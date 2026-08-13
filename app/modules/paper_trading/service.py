from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApplicationError
from app.modules.paper_trading.models import (
    PaperAccount,
    PaperAccountResetEvent,
    PaperExecution,
    PaperOrder,
    PaperPosition,
    utc_now,
)
from app.modules.paper_trading.quote_provider import (
    PaperTradingQuote,
    PaperTradingQuoteProvider,
    normalize_symbol,
)
from app.modules.paper_trading.schemas import (
    PaperAccountResponse,
    PaperExecutionResponse,
    PaperOrderCreateRequest,
    PaperOrderCreateResponse,
    PaperOrderResponse,
    PaperPortfolioResponse,
    PaperPortfolioSummaryResponse,
    PaperPositionResponse,
)


MONEY_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.0001")
PERCENT_QUANT = Decimal("0.01")
logger = logging.getLogger(__name__)


class PaperTradingService:
    def __init__(
        self,
        db: Session,
        quote_provider: PaperTradingQuoteProvider,
        settings: Settings,
        user_id: int | None = None,
    ) -> None:
        self._db = db
        self._quote_provider = quote_provider
        self._settings = settings
        self._user_id = user_id

    def set_user(self, user_id: int | None) -> None:
        self._user_id = user_id

    def get_portfolio(self) -> PaperPortfolioResponse:
        try:
            account = self._get_or_create_account()
            portfolio = self._build_portfolio(account)
            self._db.commit()
            return portfolio
        except Exception:
            self._db.rollback()
            raise

    def list_positions(self) -> list[PaperPositionResponse]:
        portfolio = self.get_portfolio()
        return portfolio.positions

    def list_orders(
        self,
        *,
        side: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PaperOrderResponse]:
        try:
            account = self._get_or_create_account()
            query: Select[tuple[PaperOrder]] = (
                select(PaperOrder)
                .where(PaperOrder.account_id == account.id)
                .order_by(PaperOrder.submitted_at.desc(), PaperOrder.id.desc())
                .limit(limit)
            )
            if side is not None:
                query = query.where(PaperOrder.side == side)
            if status is not None:
                query = query.where(PaperOrder.status == status)
            orders = [
                PaperOrderResponse.model_validate(order)
                for order in self._db.scalars(query).all()
            ]
            self._db.commit()
            return orders
        except Exception:
            self._db.rollback()
            raise

    def place_order(self, request: PaperOrderCreateRequest) -> PaperOrderCreateResponse:
        symbol = normalize_symbol(request.symbol)
        quote = self._quote_provider.get_quote(symbol)
        try:
            if request.side == "buy":
                order, execution, account = self._buy(symbol, quote, request.quantity)
            elif request.side == "sell":
                order, execution, account = self._sell(symbol, quote, request.quantity)
            else:
                raise ApplicationError("Unsupported paper trading order side.", status_code=422)

            summary = self._build_portfolio(account).summary
            response = PaperOrderCreateResponse(
                order=PaperOrderResponse.model_validate(order),
                execution=PaperExecutionResponse.model_validate(execution),
                summary=summary,
            )
            self._db.commit()
            return response
        except Exception:
            self._db.rollback()
            raise

    def reset_account(self) -> PaperPortfolioResponse:
        if self._user_id is None:
            raise ApplicationError("Authentication is required to reset a paper trading account.", status_code=401)

        try:
            account = self._get_or_create_account()
            self._db.execute(delete(PaperExecution).where(PaperExecution.account_id == account.id))
            self._db.execute(delete(PaperOrder).where(PaperOrder.account_id == account.id))
            self._db.execute(delete(PaperPosition).where(PaperPosition.account_id == account.id))

            initial_cash = _money(self._settings.paper_trading_initial_cash)
            account.currency = self._settings.paper_trading_currency
            account.initial_cash = initial_cash
            account.available_cash = initial_cash
            account.updated_at = utc_now()
            self._db.add(
                PaperAccountResetEvent(
                    account_id=account.id,
                    user_id=self._user_id,
                    result="success",
                )
            )
            self._db.flush()
            portfolio = self._build_portfolio(account)
            self._db.commit()
            return portfolio
        except Exception:
            self._db.rollback()
            self._record_failed_reset()
            raise

    def _record_failed_reset(self) -> None:
        try:
            account = self._db.scalar(
                select(PaperAccount).where(PaperAccount.account_key == self._account_key())
            )
            if account is None or self._user_id is None:
                self._db.rollback()
                return
            self._db.add(
                PaperAccountResetEvent(
                    account_id=account.id,
                    user_id=self._user_id,
                    result="failure",
                )
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.exception(
                "Failed to record paper account reset failure",
                extra={"user_id": self._user_id},
            )

    def _buy(
        self,
        symbol: str,
        quote: PaperTradingQuote,
        quantity: int,
    ) -> tuple[PaperOrder, PaperExecution, PaperAccount]:
        account = self._get_or_create_account()
        self._validate_quote_currency(account, quote)
        amount = _money(quote.price * quantity)
        if account.available_cash < amount:
            raise ApplicationError("Insufficient paper trading cash.", status_code=409)

        position = self._get_position(account.id, symbol)
        filled_at = utc_now()
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side="buy",
            order_type="market",
            quantity=quantity,
            status="filled",
            submitted_at=filled_at,
            filled_at=filled_at,
        )
        self._db.add(order)
        self._db.flush()
        execution = self._create_execution(
            account=account,
            order=order,
            quote=quote,
            quantity=quantity,
            executed_at=filled_at,
        )
        account.available_cash = _money(account.available_cash - amount)

        if position is None:
            self._db.add(
                PaperPosition(
                    account_id=account.id,
                    symbol=symbol,
                    name=quote.name,
                    currency=quote.currency,
                    quantity=quantity,
                    average_cost=_price(quote.price),
                )
            )
        else:
            old_quantity = position.quantity
            new_quantity = old_quantity + quantity
            new_average_cost = (
                (old_quantity * position.average_cost) + (quantity * quote.price)
            ) / new_quantity
            position.quantity = new_quantity
            position.average_cost = _price(new_average_cost)
            position.name = quote.name
            position.currency = quote.currency

        return order, execution, account

    def _sell(
        self,
        symbol: str,
        quote: PaperTradingQuote,
        quantity: int,
    ) -> tuple[PaperOrder, PaperExecution, PaperAccount]:
        account = self._get_or_create_account()
        self._validate_quote_currency(account, quote)
        position = self._get_position(account.id, symbol)
        if position is None:
            raise ApplicationError("Paper trading position not found.", status_code=404)
        if position.quantity < quantity:
            raise ApplicationError("Insufficient paper trading holdings.", status_code=409)

        filled_at = utc_now()
        order = PaperOrder(
            account_id=account.id,
            symbol=symbol,
            side="sell",
            order_type="market",
            quantity=quantity,
            status="filled",
            submitted_at=filled_at,
            filled_at=filled_at,
        )
        self._db.add(order)
        self._db.flush()
        execution = self._create_execution(
            account=account,
            order=order,
            quote=quote,
            quantity=quantity,
            executed_at=filled_at,
        )
        account.available_cash = _money(account.available_cash + quote.price * quantity)
        remaining_quantity = position.quantity - quantity
        if remaining_quantity == 0:
            self._db.delete(position)
        else:
            position.quantity = remaining_quantity
            position.name = quote.name
            position.currency = quote.currency

        return order, execution, account

    def _get_or_create_account(self) -> PaperAccount:
        account_key = self._account_key()
        account = self._db.scalar(
            select(PaperAccount).where(PaperAccount.account_key == account_key)
        )
        if account is not None:
            return account

        initial_cash = _money(self._settings.paper_trading_initial_cash)
        account = PaperAccount(
            account_key=account_key,
            user_id=self._user_id,
            currency=self._settings.paper_trading_currency,
            initial_cash=initial_cash,
            available_cash=initial_cash,
        )
        self._db.add(account)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            account = self._db.scalar(
                select(PaperAccount).where(PaperAccount.account_key == account_key)
            )
            if account is None:
                raise
        return account

    def _account_key(self) -> str:
        if self._user_id is None:
            return self._settings.paper_trading_demo_account_key
        return f"user:{self._user_id}"

    def _get_position(self, account_id: int, symbol: str) -> PaperPosition | None:
        return self._db.scalar(
            select(PaperPosition).where(
                PaperPosition.account_id == account_id,
                PaperPosition.symbol == symbol,
            )
        )

    def _create_execution(
        self,
        *,
        account: PaperAccount,
        order: PaperOrder,
        quote: PaperTradingQuote,
        quantity: int,
        executed_at,
    ) -> PaperExecution:
        execution = PaperExecution(
            order_id=order.id,
            account_id=account.id,
            symbol=quote.symbol,
            side=order.side,
            quantity=quantity,
            price=_price(quote.price),
            executed_at=executed_at,
        )
        self._db.add(execution)
        self._db.flush()
        return execution

    def _validate_quote_currency(
        self,
        account: PaperAccount,
        quote: PaperTradingQuote,
    ) -> None:
        if quote.currency != account.currency:
            raise ApplicationError(
                (
                    "Paper trading account currency does not match quote currency; "
                    "FX conversion is not supported."
                ),
                status_code=422,
            )

    def _build_portfolio(self, account: PaperAccount) -> PaperPortfolioResponse:
        positions = self._db.scalars(
            select(PaperPosition)
            .where(PaperPosition.account_id == account.id)
            .order_by(PaperPosition.symbol.asc())
        ).all()

        position_responses: list[PaperPositionResponse] = []
        market_value = Decimal("0")
        for position in positions:
            quote = self._quote_provider.get_quote(position.symbol)
            self._validate_quote_currency(account, quote)
            current_price = _price(quote.price)
            position_market_value = _money(position.quantity * current_price)
            unrealized_profit_loss = _money(
                (current_price - position.average_cost) * position.quantity
            )
            unrealized_profit_loss_percent = _percent(
                (
                    (current_price - position.average_cost)
                    / position.average_cost
                    * Decimal("100")
                )
                if position.average_cost
                else Decimal("0")
            )
            market_value += position_market_value
            position_responses.append(
                PaperPositionResponse(
                    symbol=position.symbol,
                    name=position.name,
                    currency=position.currency,
                    quantity=position.quantity,
                    average_cost=_price(position.average_cost),
                    current_price=current_price,
                    market_value=position_market_value,
                    unrealized_profit_loss=unrealized_profit_loss,
                    unrealized_profit_loss_percent=unrealized_profit_loss_percent,
                )
            )

        market_value = _money(market_value)
        total_assets = _money(account.available_cash + market_value)
        total_profit_loss = _money(total_assets - account.initial_cash)
        total_profit_loss_percent = _percent(
            (total_profit_loss / account.initial_cash * Decimal("100"))
            if account.initial_cash
            else Decimal("0")
        )
        position_ratio = _percent(
            (market_value / total_assets * Decimal("100"))
            if total_assets
            else Decimal("0")
        )

        return PaperPortfolioResponse(
            account=PaperAccountResponse(
                id=account.id,
                account_key=account.account_key,
                currency=account.currency,
                initial_cash=_money(account.initial_cash),
                available_cash=_money(account.available_cash),
            ),
            summary=PaperPortfolioSummaryResponse(
                initial_cash=_money(account.initial_cash),
                available_cash=_money(account.available_cash),
                market_value=market_value,
                total_assets=total_assets,
                total_profit_loss=total_profit_loss,
                total_profit_loss_percent=total_profit_loss_percent,
                position_ratio=position_ratio,
            ),
            positions=position_responses,
        )

    def count_records(self) -> tuple[int, int, int, int]:
        counts = (
            self._db.scalar(select(func.count()).select_from(PaperAccount)) or 0,
            self._db.scalar(select(func.count()).select_from(PaperPosition)) or 0,
            self._db.scalar(select(func.count()).select_from(PaperOrder)) or 0,
            self._db.scalar(select(func.count()).select_from(PaperExecution)) or 0,
        )
        self._db.commit()
        return counts


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PRICE_QUANT, rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)
