# Draft — Creator Recipe Day (2026-07-13)

> Reference example of the full loop: drafted first, published with heavy additions, and
> the draft-vs-real diff drove the 2026-07-13 rewrite of `../IMPROVE_PROMPT.md`
> (elicitation block, specificity pass, build-log rule, humor license, length-follows-type).

## Inputs

- Event: Creator Recipe Day — vooy(부이) 팀 주최, 해시드 라운지. 3rd prize.
- Built: video cut-editing agent = vooy + my own MCP server; live demo cutting footage
  filmed on site.
- Elicited: demo = cut editing; stack = vooy with custom MCP (MCP server was mine);
  solo (no co-host block); images to be added by hand; no link line.
- Reference scraped: host Donghyun Kim's post (repost of the BZCF 비즈까페 event writeup)
  — https://www.linkedin.com/feed/update/urn:li:activity:7482253088116867073/

## Korean (LinkedIn)

지난 주말, vooy(부이) 팀이 해시드 라운지에서 연 Creator Recipe Day에 다녀왔습니다.

크리에이터, 인플루언서, 개발자분들이 모여서 각자 AI 에이전트로 뭔가를 만들어 발표하는 자리였는데요. 다들 들고 온 것들이 기발해서 구경하는 재미가 쏠쏠했습니다.

vooy는 '해줘' 하면 해주는 AI 에이전트인데, 여기에 제가 직접 만든 MCP 서버를 붙여서 영상 컷 편집을 자동으로 해주는 에이전트를 만들었습니다. 마침 현장에서 촬영 중이던 footage를 그대로 받아서, 그 자리에서 컷 편집본을 뽑아보는 데모를 했어요.

필요한 도구를 그날 바로 만들어서 현장에서 써본다는 게, AI로 일하는 방식이 여기까지 왔구나 싶어 재미있었습니다.

감사하게도 3등을 했습니다. 쟁쟁한 분들이 많아서 큰 기대 없이 갔는데, 상까지 받으니 기분이 좋네요. (1, 2등 결과물도 정말 인상적이었습니다.)

좋은 자리 만들어주신 vooy 팀과 해시드 팀 감사합니다. 한국에서도 이런 자리가 더 많아지면 좋겠습니다.

## English (LinkedIn)

Last weekend I joined **Creator Recipe Day**, hosted by the vooy team at Hashed Lounge.

Creators, influencers, and developers gathered to each build something with an AI agent and demo it. The range of ideas people brought was genuinely fun to watch.

vooy is an AI agent that just does what you ask it to. I hooked it up to an MCP server I built myself, so it could edit video cuts automatically. I grabbed footage being filmed at the venue and assembled a rough cut on the spot as a live demo.

Building the exact tool you need that same day and using it right there on site — it was a real reminder of how far working with AI has come.

Grateful to have placed 3rd. I came in against a strong field with low expectations, so the prize was a nice surprise (the 1st and 2nd builds were excellent too).

Thanks to the vooy and Hashed teams for putting this together. I'd love to see more gatherings like this in Korea.

## Outcome

- Published: https://www.linkedin.com/feed/update/urn:li:activity:7482320413042139136/
- Archived: `../posts/2026-07-13_7482320413042139136/` (4 images)
- Skeleton transferred near-verbatim (opening line, the vooy+MCP core sentence, the
  thanks/close) — structure and technical framing worked.
- Biggest deviations — what the real post added that the draft lacked:
  - A **story opening** (expected AI 안경잡이들 → 미모의 인플루언서들, "이게 뭐지...?",
    화지님) instead of a summary opening.
  - **Real names + the exact prize**: 민웅기 님 (interview), 3등 = 파인다이닝 20만원권
    ("예약도 해주신다").
  - An honest **build-log paragraph** (personal API had no MCP → most of the time went
    into building the MCP server) + a forward-looking take (ship a service as *just* an
    MCP — Midjourney-on-Discord analogy).
  - **Generous concrete descriptions of the 1st/2nd builds** (cold-email sponsorship agent
    that got a real rejection ㅋㅋㅋ; influencer-finder "marketing or flirting" agent) and
    ㅋㅋㅋ humor throughout.
- → These gaps became IMPROVE_PROMPT.md's elicitation inputs (SCENE / PEOPLE / CONCRETE /
  HARD_PART / OTHERS), the specificity pass, the build-log rule, the humor license, and
  the length-follows-type rule.
