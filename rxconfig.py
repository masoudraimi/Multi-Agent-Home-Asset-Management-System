import reflex as rx
from reflex_components_radix.plugin import RadixThemesPlugin
from reflex_base.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="rxapp",
    frontend_port=3000,
    backend_port=8001,
    plugins=[
        RadixThemesPlugin(
            theme=rx.theme(
                appearance="dark",
                accent_color="violet",
                gray_color="slate",
                radius="medium",
            )
        )
    ],
    disable_plugins=[SitemapPlugin],
)
