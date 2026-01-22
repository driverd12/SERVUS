from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)

@dataclass(frozen=True)
class ADConfig:
    host: str
    username: str
    password: str

@dataclass(frozen=True)
class OktaConfig:
    domain: str
    token: str
    app_google: str | None = None
    app_slack: str | None = None
    app_zoom: str | None = None
    app_ramp: str | None = None
    dirintegration_ad_import: str | None = None

@dataclass(frozen=True)
class ServusConfig:
    ad: ADConfig
    okta: OktaConfig

def load_config() -> ServusConfig:
    ad = ADConfig(
        host=env("SERVUS_AD_HOST",""),
        username=env("SERVUS_AD_USERNAME",""),
        password=env("SERVUS_AD_PASSWORD",""),
    )
    okta = OktaConfig(
        domain=env("SERVUS_OKTA_DOMAIN",""),
        token=env("SERVUS_OKTA_TOKEN",""),
        app_google=env("SERVUS_OKTA_APP_GOOGLE"),
        app_slack=env("SERVUS_OKTA_APP_SLACK"),
        app_zoom=env("SERVUS_OKTA_APP_ZOOM"),
        app_ramp=env("SERVUS_OKTA_APP_RAMP"),
        dirintegration_ad_import=env("SERVUS_OKTA_DIRINTEGRATION_AD_IMPORT"),
    )

    missing = []
    if not ad.host: missing.append("SERVUS_AD_HOST")
    if not ad.username: missing.append("SERVUS_AD_USERNAME")
    if not ad.password or ad.password == "__SET_ME__": missing.append("SERVUS_AD_PASSWORD")
    if not okta.domain: missing.append("SERVUS_OKTA_DOMAIN")
    if not okta.token or okta.token == "__SET_ME__": missing.append("SERVUS_OKTA_TOKEN")
    if missing:
        raise RuntimeError("Missing required config: " + ", ".join(missing))
    return ServusConfig(ad=ad, okta=okta)
