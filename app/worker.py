from .auth import bootstrap_user
from .db import migrate
from .jobs import run_forever


if __name__ == "__main__":
    migrate()
    bootstrap_user()
    run_forever()
