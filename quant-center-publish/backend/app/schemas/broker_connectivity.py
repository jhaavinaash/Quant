from pydantic import BaseModel


class BrokerConnectivityItem(BaseModel):
    name: str
    status: str
