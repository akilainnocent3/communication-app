from drf_spectacular.extensions import OpenApiAuthenticationExtension


class DeviceTokenScheme(OpenApiAuthenticationExtension):
    target_class = "modules.devices.api.auth.DeviceTokenAuthentication"
    name = "deviceToken"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "description": "Short-lived device access token from POST /device/auth/token/."}
