import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.conf.app_config import DBConfig, app_config


class MysqlClientManager:
    def __init__(self,db_config):
        self.db_config:DBConfig|None=db_config
        self.engine:AsyncEngine|None=None
        self.session_factory=None

    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"

    def init(self):
        self.engine=create_async_engine(self._get_url(), pool_size=10,pool_pre_ping=True)
        self.session_factory=async_sessionmaker(self.engine,autoflush=True,expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()

dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()
    engine=dw_mysql_client_manager.engine

    # def __call__(self, **local_kw: Any) -> _AS:
    #     """Produce a new :class:`.AsyncSession` object using the configuration
    #     established in this :class:`.async_sessionmaker`.
    #
    #     In Python, the ``__call__`` method is invoked on an object when
    #     it is "called" in the same way as a function::
    #
    #         AsyncSession = async_sessionmaker(async_engine, expire_on_commit=False)
    #         session = AsyncSession()  # invokes sessionmaker.__call__()
    #这里的类后面加括号，就相当于调用__call__方法
    async def test():
        async with dw_mysql_client_manager.session_factory() as session:
            #autoflush = True, 自动将数据更改同步到数据库
            # expire_on_commit = False 异步需要关闭，用不了
            sql="select * from fact_order limit 10"
            result=await session.execute(text(sql))
            #字典
            rows=result.mappings().all()
            print(type(rows))
            print(type(rows[0]))
            print(rows[0])

            #元组
            # rows=result.all()
            # print(type(rows))
            # print(type(rows[0]))
            # print(rows[0])

            # 两个参数补充说明
            # autoflush = True
            # 执行查询前自动把未提交的修改同步到数据库
            # 异步 / 同步都推荐开启
            # expire_on_commit = False
            # 异步专属必配参数
            # 同步代码一般不用管，默认
            # True
            #可异步里，任何数据库操作必须带 await没有 await = 同步操作 = 违反规则 = 报错异步会话只允许你手动写 await 去查库，绝不允许内部自动同步查库。
            # 设置
            # expire_on_commit = False
            # 解决了什么？
            # 设置后：
            # commit()
            # 之后不会标记对象为失效
            # 对象属性保留在内存中
            # 你可以直接访问属性，不需要重新查库
            # 完全避免异步上下文不允许同步查询的报错

            # 1.
            # 先看默认行为（同步 / 异步都是
            # True）
            # SQLAlchemy
            # 默认
            # expire_on_commit = True：
            # 执行
            # session.commit()
            # 后
            # 所有从数据库查询出来的对象都会被标记为 “失效”
            # 下次你访问对象属性（比如
            # user.name）
            # 会自动重新查询数据库获取最新数据
            # 这在同步代码里没问题，因为同步会话可以安全重查。


    asyncio.run(test())
