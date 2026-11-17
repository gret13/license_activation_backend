if __name__ == "__main__":
    import asyncio

    from app.db.bootstrap import bootstrap

    asyncio.run(bootstrap())
