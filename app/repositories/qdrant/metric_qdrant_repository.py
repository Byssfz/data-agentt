from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams,Distance,PointStruct

from app.conf.app_config import app_config
from app.entities.metric_info import MetricInfo


class MetricQdrantRepository:
    collection_name="metric_info_collection"

    def __init__(self,client:AsyncQdrantClient):
        self.client=client

    async def ensure_collection(self):
        if not await self.client.collection_exists(collection_name=self.collection_name):
            await self.client.create_collection(collection_name=self.collection_name,vectors_config=VectorParams(
                size=app_config.qdrant.embedding_size,distance=Distance.COSINE)
                )

    async def upsert(self, ids, payloads, embeddings,batch_size:int=10):
        points:list[PointStruct]=[PointStruct(id=id,payload=payload,vector=embedding) for id,payload,embedding in zip(ids,payloads,embeddings)]
        for i in range(0, len(points), batch_size):
            await self.client.upsert(collection_name=self.collection_name, points=points[i:i + batch_size])

    async def search(self, embedding,score_threshold: float = 0.6, limit: int = 20):
        result=await self.client.query_points(collection_name=self.collection_name,query=embedding,score_threshold=score_threshold,limit=limit)
        return [MetricInfo(**point.payload) for point in result.points]