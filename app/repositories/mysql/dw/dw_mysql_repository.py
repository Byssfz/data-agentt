from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DWMySQLRepository:
    def __init__(self,session:AsyncSession):
        self.session:AsyncSession|None=session


    async def get_column_types(self,table_name:str)->dict[str,str]:
        sql=f"show columns from {table_name}"
        result=await self.session.execute(text(sql))
        result_dict=result.mappings().fetchall()
        return {row['Field']: row['Type']for row in result_dict}

    async def get_column_values(self, table_name: str, column_name: str, limit: int):
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        result = await self.session.execute(text(sql))
        return [row[0] for row in result]

    async def get_db_info(self):
        sql="select version()"
        result=await self.session.execute(text(sql))
        version=result.scalar()

        dialect = self.session.get_bind().dialect.name

        return {"dialect":dialect,"version":version}

    async def validate(self, sql):
        sql=f"explain {sql}"
        await self.session.execute(text(sql))

    async def run(self, sql):
        result=await self.session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]
