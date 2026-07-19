from fastapi import APIRouter
from app.api.v1.endpoints import auth, broker, broker_session, dashboard, execution, instrument, positions, production_brokers, signals, engines, settings, trades, trade_entry, ai_scanner, f1, f1_basket, market_briefing

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(broker.router, prefix="/broker", tags=["broker"])
api_router.include_router(production_brokers.router, prefix="/brokers/production", tags=["production-brokers"])
api_router.include_router(broker_session.router, prefix="/broker_session", tags=["broker_session"])
api_router.include_router(instrument.router, prefix="/instrument", tags=["instrument"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(execution.router, prefix="/execution", tags=["execution"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(market_briefing.router, prefix="/market-briefing", tags=["market-briefing"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(trade_entry.router, prefix="/trade-entry", tags=["trade-entry"])
api_router.include_router(ai_scanner.router, prefix="/ai-scanner", tags=["ai-scanner"])
api_router.include_router(f1.router, prefix="/f1", tags=["f1"])
api_router.include_router(f1_basket.router, prefix="/f1-basket", tags=["f1-basket"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(engines.router, prefix="/engines", tags=["engines"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])