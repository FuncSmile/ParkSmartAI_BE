"""CLI helper to manage IoT devices & API keys."""

import argparse
from tabulate import tabulate

from app.database import Base, engine, get_session
from app import crud
from app.models import IoTDevice


def ensure_db():
    Base.metadata.create_all(bind=engine)


def cmd_list(args):
    with get_session() as session:
        devices = crud.list_devices(session)
        table = [
            [
                d.id,
                d.slot_id,
                d.api_key,
                "active" if d.is_active else "disabled",
                d.last_seen,
                d.description or "",
            ]
            for d in devices
        ]
        print(tabulate(table, headers=["id", "slot", "api_key", "status", "last_seen", "desc"]))


def cmd_create(args):
    with get_session() as session:
        device = crud.create_device(session, slot_id=args.slot_id, description=args.description)
        session.commit()
        print("Created:", device.id, device.slot_id, device.api_key)


def cmd_disable(args):
    with get_session() as session:
        dev = crud.set_device_active(session, args.id, False)
        session.commit()
        if dev:
            print("Disabled", dev.id)
        else:
            print("Device not found")


def cmd_enable(args):
    with get_session() as session:
        dev = crud.set_device_active(session, args.id, True)
        session.commit()
        if dev:
            print("Enabled", dev.id)
        else:
            print("Device not found")


def cmd_regen(args):
    with get_session() as session:
        dev = crud.regenerate_api_key(session, args.id)
        session.commit()
        if dev:
            print("New key:", dev.api_key)
        else:
            print("Device not found")


def main():
    ensure_db()
    parser = argparse.ArgumentParser(description="Manage IoT devices & API keys")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_create = sub.add_parser("create")
    p_create.add_argument("slot_id")
    p_create.add_argument("-d", "--description", default=None)
    p_create.set_defaults(func=cmd_create)

    p_disable = sub.add_parser("disable")
    p_disable.add_argument("id", type=int)
    p_disable.set_defaults(func=cmd_disable)

    p_enable = sub.add_parser("enable")
    p_enable.add_argument("id", type=int)
    p_enable.set_defaults(func=cmd_enable)

    p_regen = sub.add_parser("regen")
    p_regen.add_argument("id", type=int)
    p_regen.set_defaults(func=cmd_regen)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
