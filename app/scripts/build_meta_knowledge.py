import argparse
import asyncio
import sys
from pathlib import Path

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manger
# print(sys.path)
from app.core.log import logger
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repositoriy import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService


async def build(config_path: Path):
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manger.init()
    embedding_client_manager.init()
    es_client_manager.init()
    async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
        meta_mysql_repository=MetaMySQLRepository(meta_session)
        dw_mysql_repository=DWMySQLRepository(dw_session)
        column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manger.client)
        value_es_reporitory=ValueESRepository(es_client_manager.client)
        metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manger.client)
        meta_knowledge_service=MetaKnowledgeService(meta_mysql_repository=meta_mysql_repository,
                                                    dw_mysql_repository=dw_mysql_repository,
                                                    column_qdrant_respository=column_qdrant_repository,
                                                    embedding_client=embedding_client_manager.client,
                                                    value_es_repository=value_es_reporitory,
                                                    metric_qdrant_repository=metric_qdrant_repository
                                                    )
        await meta_knowledge_service.build(config_path)
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manger.close()
    await es_client_manager.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--conf")  # option that takes a value

    args = parser.parse_args()

    config_path = Path(args.conf)

    asyncio.run(build(config_path))










# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt> python .\app\scripts\meta_knowledge_service.py
# Traceback (most recent call last):
#   File "C:\Users\14912\Desktop\Code\PyCharm\data-agentt\app\scripts\meta_knowledge_service.py", line 4, in <module>
#     from app.core.log import logger
# ModuleNotFoundError: No module named 'app'
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt> python .\app\scripts\meta_knowledge_service.py
# ['C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\app\\scripts', 'C:\\Program Files\\Python313\\python313.zip', 'C:\\Program Files\\Python313\\DLLs', 'C:\\Program Files\\Python313\\Lib', 'C:\\Program Files\\Python313', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32\\lib', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\Pythonwin']
# Traceback (most recent call last):
#   File "C:\Users\14912\Desktop\Code\PyCharm\data-agentt\app\scripts\meta_knowledge_service.py", line 5, in <module>
#     from app.core.log import logger
# ModuleNotFoundError: No module named 'app'
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt> python -m app.scripts.meta_knowledge_service.py
# ['C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt', 'C:\\Program Files\\Python313\\python313.zip', 'C:\\Program Files\\Python313\\DLLs', 'C:\\Program Files\\Python313\\Lib', 'C:\\Program Files\\Python313', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32\\lib', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\Pythonwin']
# C:\Users\14912\Desktop\Code\PyCharm\data-agentt\.venv\Scripts\python.exe: Error while finding module specification for 'app.scripts.meta_knowledge_service.py' (ModuleNotFoundError: __path__ attribute not found on 'app.scripts.build_meta_knowledge' while trying to find 'app.scripts.meta_knowledge_service.py'). Try using 'app.scripts.build_meta_knowledge' instead of 'app.scripts.meta_knowledge_service.py' as the module name.
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt> python -m app.scripts.build_meta_knowledge
# ['C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt', 'C:\\Program Files\\Python313\\python313.zip', 'C:\\Program Files\\Python313\\DLLs', 'C:\\Program Files\\Python313\\Lib', 'C:\\Program Files\\Python313', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32\\lib', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\Pythonwin']
# 2026-06-05 16:40:08.858 | INFO     | __main__:build:11 - Building.....
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt> cd app
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt\app> python -m app.scripts.build_meta_knowledge
# C:\Users\14912\Desktop\Code\PyCharm\data-agentt\.venv\Scripts\python.exe: Error while finding module specification for 'app.scripts.build_meta_knowledge' (ModuleNotFoundError: No module named 'app')
# (data-agentt) PS C:\Users\14912\Desktop\Code\PyCharm\data-agentt\app> python -m scripts.build_meta_knowledge
# ['C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\app', 'C:\\Program Files\\Python313\\python313.zip', 'C:\\Program Files\\Python313\\DLLs', 'C:\\Program Files\\Python313\\Lib', 'C:\\Program Files\\Python313', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\win32\\lib', 'C:\\Users\\14912\\Desktop\\Code\\PyCharm\\data-agentt\\.venv\\Lib\\site-packages\\Pythonwin']
# Traceback (most recent call last):
#   File "<frozen runpy>", line 198, in _run_module_as_main
#   File "<frozen runpy>", line 88, in _run_code
#   File "C:\Users\14912\Desktop\Code\PyCharm\data-agentt\app\scripts\meta_knowledge_service.py", line 5, in <module>
#     from app.core.log import logger
# ModuleNotFoundError: No module named 'app'