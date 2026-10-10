from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CsrfSessionScheme(OpenApiAuthenticationExtension):
    target_class = "common.auth.CsrfSessionAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "cm_session"}
