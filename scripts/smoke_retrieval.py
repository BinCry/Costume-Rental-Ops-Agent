import asyncio

from app.knowledge.repository import close_pool, open_pool
from app.knowledge.service import search_knowledge
from app.models import ActorContext


async def main() -> None:
    open_pool()
    try:
        actor = ActorContext(user_id="smoke-test", audiences=("customer", "shared"))
        results = await search_knowledge(actor, "Tôi trả trễ thì có bị tính phí không?", 3)
        if not results:
            raise RuntimeError("Retrieval returned no results")
        print(f"Retrieval smoke test passed: {len(results)} results")
        for result in results:
            print(f"  {result.score:.3f} - {result.document_id}")
    finally:
        close_pool()


if __name__ == "__main__":
    asyncio.run(main())
