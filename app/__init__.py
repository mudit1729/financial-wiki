from flask import Flask

from app.config import get_config
from app.extensions import db, migrate


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    migrate.init_app(app, db)

    from app import cli
    from app.routes.backtests import bp as backtests_bp
    from app.routes.companies import bp as companies_bp
    from app.routes.documents import bp as documents_bp
    from app.routes.investors import bp as investors_bp
    from app.routes.macro import bp as macro_bp
    from app.routes.main import bp as main_bp
    from app.routes.rag import bp as rag_bp
    from app.routes.strategies import bp as strategies_bp
    from app.routes.themes import bp as themes_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(rag_bp)
    app.register_blueprint(backtests_bp)
    app.register_blueprint(themes_bp)
    app.register_blueprint(strategies_bp)
    app.register_blueprint(investors_bp)
    app.register_blueprint(macro_bp)
    cli.register(app)

    return app
