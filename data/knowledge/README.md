# 지식 자료 자리

> 초기 베이스 안내 문서이며 실행 중 대화 모델은 이 Markdown을 읽지 않는다. 현재는 `facts.json`만 `services/retriever.py`가 장면·인물·단서로 필터링해 사용한다. `example_lore.md`는 베이스 예시로 남겨 두었다. [문서 지도](../../docs/README.md)

팀이 챗봇의 답변에 사용할 문서를 준비하는 곳입니다. 예시 경로일 뿐이므로 데이터 형식과 검색 저장소는 팀이 선택할 수 있습니다. 개인정보, 저작권이 확인되지 않은 자료, 실제 API 키는 넣지 마세요.

`example_lore.md`는 검색 흐름을 실험할 수 있는 초기 베이스의 가상 자료이며 현재 대화에는 사용하지 않습니다. 실제 답변에는 `facts.json`에서 현재 인물·장면·단서에 허용된 사실만 검색해 반영합니다. 자료 검색은 `services/retriever.py`, 답변 생성은 `services/generator.py`, 연결은 `services/chatbot_service.py`에서 담당합니다.
