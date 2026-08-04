import asyncio
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from database.engine import async_session_factory
from database.models import User, Dream, Task, WithdrawalRequest

async def main():
    async with async_session_factory() as session:
        # Update Users
        res = await session.execute(select(User))
        for u in res.scalars():
            flag_modified(u, 'name')
            flag_modified(u, 'surname')
            flag_modified(u, 'phone_number')
        
        # Update Dreams
        res = await session.execute(select(Dream))
        for d in res.scalars():
            flag_modified(d, 'dream_name')
            
        # Update Tasks
        res = await session.execute(select(Task))
        for t in res.scalars():
            flag_modified(t, 'title')
            flag_modified(t, 'description')

        # Update Withdrawal Requests (Encrypted credit cards)
        res = await session.execute(select(WithdrawalRequest))
        for w in res.scalars():
            flag_modified(w, 'card_number')
            
        await session.commit()
        print("Successfully encrypted all existing data!")

if __name__ == "__main__":
    asyncio.run(main())
