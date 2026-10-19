"""Offline English display translations of Korean game-table text.

These are editor labels, not patches to game data. Keep numbers, units, placeholders,
IDs and effect claims from the source. Unknown text remains visible in its original form.
"""
from functools import lru_cache
import re

HANGUL = re.compile('[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]')

EXACT = {
 '파츠 가루 U 를 이용하여 미트론 크리스탈을 만들 수 있는 스킬북입니다. (마우스 우클릭으로 스킬을 배울 수 있습니다)':'A skill book for crafting Mittron Crystal from Ultra Parts Powder. Right-click to learn the skill.',
 '네오 무기 슬롯 확장 아이템을 만들 수 있는 스킬북입니다. (마우스 우클릭으로 스킬을 배울 수 있습니다)':'A skill book for crafting a Neo weapon slot expansion item. Right-click to learn the skill.',
 '이름':'Name', '파일 이름':'File name', '레벨':'Level', '최고속도':'Maximum speed',
 '정렬 순서':'Sort order', '자동차ID':'Car ID', '차량 등급':'Car grade', '오픈시기':'Release stage',
 '자동차명':'Car name', '게시판 말머리 (시승기,튜닝)':'Forum category (test drive, tuning)',
 '메이커':'Manufacturer', '쿠폰 차량':'Coupon car', '업그레이드 등급':'Upgrade grade',
 '요구레벨':'Required level', '등급 구분':'Grade type', '차량 설명':'Car description',
 '질문':'Question','정 답':'Correct answer','경험치':'EXP','성공여부':'Success flag',
 '펄스간격':'Pulse interval','이벤트':'Event','장갑차 레이저 간격':'Armored-car laser interval',
 '장갑차 레이져 켜지는 시간':'Armored-car laser activation time','연막 간격/이벤트간격':'Smoke / event interval',
 '연막 시간':'Smoke duration','컨버팅시간':'Conversion time','Skill거리':'Skill range',
 'w-탐색주기':'Weapon search interval','w-회피비율':'Weapon evasion rate',
 '뒤':'Rear','앞':'Front','추가갯수':'Additional count','추가속도':'Additional speed',
 'UI 끝 단위':'UI value suffix','회':'times','분':'minutes','시간(분)':'Time (minutes)',
 '게임모드수행':'Game mode completions','곡예주행횟수':'Artistic driving count','드리프트횟수':'Drift count',
 '러쉬타임 도전':'Rush Time attempts','리얼매치 상위랭크':'Real Match top ranks','배틀횟수':'Battle count',
 '언더시티':'Undercity','역주행시간':'Wrong-way driving time','인덱스':'Index','점프횟수':'Jump count',
 '종류':'Type','주행시간':'Driving time','증정카(쿠폰)이름':'Reward car (coupon) name',
 '체이싱 횟수':'Chase count','최대슬롯갯수':'Maximum slot count','카 Unique ID':'Car unique ID',
 '카 등급':'Car grade','콤보횟수':'Combo count','쿠폰ID':'Coupon ID','쿠폰타입별':'By coupon type',
 '퀘스트클리어':'Quest completions','퀵서비스횟수':'Delivery count','튜토리얼 쿠폰용':'Tutorial coupon',
 '튜토리얼용':'Tutorial','횟수':'Count','/명령어':'/Command','카테고리상수':'Category constant',
 '카테고리':'Category','욕설':'Profanity','타이어':'Tire','캐릭터명 필터':'Character name filter',
 '요구 Level (이상)':'Minimum required level','요구 등급 (이상)':'Minimum required grade',
 '사전 수행 Unique_ID (and)':'Prerequisite unique IDs (all required)','요구 평판 (타입)':'Required reputation type',
 '요구 평판(이상)':'Minimum required reputation','요구 Item':'Required item',
 '시작 요구 License':'License required to start','완료 요구 License':'License required to complete',
 '반복 Quest Flag':'Repeatable quest flag','진형 조건 Flag':'Faction requirement flag',
 '별 종류':'Star type','속도 선택 사용':'Use speed selection','별 포인트':'Star points',
 '초보 최소 인원':'Minimum beginner players','초보 최대 인원':'Maximum beginner players',
 '프로 최소 인원':'Minimum pro players','프로 최대 인원':'Maximum pro players',
 '미국전용':'US only','한국 전용':'Korea only','없음':'None',
 'AI타입':'AI type','단거리 무기 최소 사거리':'Short-range weapon minimum range',
 '단거리 무기 최대 사거리':'Short-range weapon maximum range','단거리 재장전 시간':'Short-range reload time',
 '장거리 무기 최소 사거리':'Long-range weapon minimum range','장거리 무기 최대 사거리':'Long-range weapon maximum range',
 '장거리 재장전 시간':'Long-range reload time','직선 충돌 MAX거리':'Maximum straight-line ram distance',
 '무기 & 충돌 공격 대기 시간':'Weapon / ram attack cooldown','조준각도':'Aim angle',
 '타겟 재탐색 시간':'Target reacquisition time','타겟 가중거리':'Target weighted distance',
 '타겟 탐색 거리':'Target search range','급 가속시의 가속값':'Burst acceleration',
 '급 가속 지속시간':'Burst acceleration duration','경계거리':'Alert distance','무기 상성':'Weapon matchup',
 '충돌데미지(장갑 종류에 따른 데미지 변화 %값)':'Ram damage modifier by armor type (%)',
 '등장 HUV ID':'Spawned HUV ID','소환 HUV ID':'Summoned HUV ID','소환 주기(초)':'Summon interval (seconds)',
 '소환 횟수':'Summon count','충돌데미지':'Ram damage','탄환수':'Ammunition count',
 '명중률(%)':'Accuracy (%)','반시야각(half degree)':'Half field of view (degrees)',
 '사정거리(m)':'Range (m)','추가 Damage 랜덤값':'Additional random damage',
 '연사횟수':'Burst shot count','연사속도':'Rate of fire','유저 무기 Cool Time(Sec)':'Player weapon cooldown (seconds)',
 'Guide(유도)':'Homing guidance','폭발타이머':'Explosion timer','부스터 게이지 소모량':'Boost gauge cost',
 '발사체 크기':'Projectile size','다이나믹 이펙트':'Dynamic effect','탄환 Speed (m/s)':'Projectile speed (m/s)',
 '내구력 (회)':'Durability (hits)','속도 (km/h)':'Speed (km/h)',
 '부딪혔을 때 가속(배)':'Acceleration on impact (multiplier)',
 '부딪혔을 때 가속(km/h)':'Acceleration on impact (km/h)',
 '부딪혔을 때 가속 시간':'Acceleration duration on impact',
 '터보사용빈도 (10초에 1회씩 몇 %)':'Turbo use chance per 10 seconds (%)',
 '앞 쪽 플레이어카 피하기 (0 : 약, 1 : 중, 2 : 강)':'Avoid players ahead (0 weak / 1 medium / 2 strong)',
 '앞 쪽 트래픽카 피하기 (0 : 약, 1 : 중, 2 : 강)':'Avoid traffic ahead (0 weak / 1 medium / 2 strong)',
 '뒤 쪽 플레이어카 피하기 (0 : 약, 1 : 중, 2 : 강)':'Avoid players behind (0 weak / 1 medium / 2 strong)',
 '보상아이템 (Reward Group)':'Reward item group',
 '가속(km/s)':'Acceleration (km/s)','감속(km/s)':'Deceleration (km/s)',
 '최고 속도(km/h)':'Maximum speed (km/h)','코너링 시 감속(km/h)':'Cornering speed reduction (km/h)',
 '부스터최고속도(km/h)':'Maximum boost speed (km/h)','부스터 가속(km/s)':'Boost acceleration (km/s)',
 '부스터지속시간(초)':'Boost duration (seconds)','부스터 사용 횟수':'Boost use count',
 '부스터 재사용 대기 시간(초)':'Boost cooldown (seconds)','부스터충전비율(x/100)':'Boost recharge rate (x/100)',
 '앞차피하기 (0~1)':'Avoid car ahead (0–1)','뒷차막기(0~1)':'Block car behind (0–1)',
 'AI 채팅 ID 입장시':'AI chat ID on entry','AI 채팅 ID 목록 중간':'AI chat IDs during race',
 'AI 채팅 ID 목록 승리':'AI chat IDs on victory','AI 채팅 ID 목록 패배':'AI chat IDs on defeat',
 'AI 채팅 ID 목록':'AI chat ID list','출현빈도(1,3,6)':'Spawn frequency (1, 3, 6)',
 '입장가능레벨 상한선':'Maximum entry level','한바퀴당경험치':'EXP per lap','한바퀴당머니':'Mito per lap',
 '문팰리스트랙':'Moon Palace track','코이노니아트랙':'Koinonia track','크라스트랙':'Cras track','오로스트랙':'Oros track',
 '쓸모 없는 스킬북':'Useless Skill Book','복귀 유저 선물상자':'Returning Player Gift Box',
 '복귀 유저가 게임에 잘 적응할 수 있도록 아이템을 제공하는 선물상자입니다.':'A gift box containing items to help returning players get back into the game.',
 'n/a (미사용)':'n/a (unused)',
 '배틀존에서 수리 중 상태일때 나와서 자동차의 속도를 100km/h 아래로 안 떨어지게 해 줍니다. S PC방전용 상품으로 PC방에서 플레이할 때만 사용할 수 있습니다.':'While repairing in the Battle Zone, prevents the car\'s speed from falling below 100 km/h. Exclusive to S PC cafes; usable only while playing at a participating PC cafe.',
 '파츠 조합 시 첨가하면 도킹 파츠를 획득할 수 있다. (파츠 상점의 조합 탭에서 사용가능)':'Add when combining parts to obtain a docking part. Use in the Combine tab of the Parts Shop.',
 '슬롯에 장착되어 검게 타버린 울트라 파츠를 다시 떼어낼 수 있다.':'Removes a scorched Ultra part from its equipped slot.',
 '울트라 파츠의 미트론 가루. 제조 아이템의 재료로 사용된다.':'Mittron powder from Ultra parts. Used as a crafting material.',
 '네오 전용 아이템을 제작할 수 있는 스킬북이 들어 있습니다. (마우스 우클릭으로 스킬북을 확인할 수 있습니다.)':'Contains a skill book for crafting Neo items. Right-click to identify the skill book.',
 '사용 즉시 적들을 교란시켜 아이템 사용자를 공격할 확률을 줄인다. (필드 퀵슬롯 아이템)':'Confuses enemies, reducing their chance to attack the user. Field quick-slot item.',
 '사용 즉시 죽은 위치에서 100% 의 내구력을 회복하여 부활합니다.':'Revives you at the location of defeat with 100% durability.',
 '사용시 무기의 2번째 슬롯이 활성화 됩니다. (지속시간 1시간)':'Unlocks the second weapon slot for 1 hour.',
 '[현재한국전용]FESTIVAL이라고 적혀있는 이벤트 응모권입니다. 이벤트 결과 발표까지 소지하고 있어야 합니다.':'[Korea only] An event entry ticket marked FESTIVAL. Keep it until the event results are announced.',
 '[현재한국전용]마일리지로 스키드샵의 마일리지 상품을 구입 할 수 있습니다.':'[Korea only] Spend mileage on mileage items in the Skid Shop.',
 '[현재한국전용]언더시티 클리어 시 원석 보상을 세트 파츠로 직접 받을 수 있게 해 줍니다.':'[Korea only] Receive set parts directly instead of ore when completing Undercity.',
 '[현재한국전용]인디아나 존스4 영화에 없어서는 안될 중요한 소품입니다. 시리즈 4편의 타이틀이기도 하죠.':'[Korea only] An essential prop from Indiana Jones 4, also featured in the film\'s title.',
 '[현재한국전용]인디아나 존스4 이벤트에 응모되었다는 확인증입니다. 이벤트 결과 발표까지 소지하고 있어야 합니다.':'[Korea only] Proof of entry in the Indiana Jones 4 event. Keep it until the results are announced.',
 '[현재한국전용]인디아나 존스의 트레이드 마크로 그는 13세에 도굴꾼을 막던 중 중절모를 얻었습니다.':'[Korea only] Indiana Jones\'s trademark fedora, acquired at age 13 while trying to stop grave robbers.',
 '[현재한국전용]인디아나 존스의 트레이드 마크로 시리즈3편을 보면 채찍을 얻는 모습을 볼 수 있습니다.':'[Korea only] Indiana Jones\'s trademark whip. The third film shows how he acquired it.',
 '이벤트에 응모되었다는 확인증입니다. 이벤트 결과 발표까지 소지하고 있어야 합니다.':'Proof of event entry. Keep it until the event results are announced.',
 'Mr.H의 세트파츠 4개를 모두 모으면 30% 충돌 감소 효과 + 출발 부스터 + 4km/h 속도 증가 + 부스트 사용시간 0.7초 증가':'Equip all 4 Mr. H set parts: collision slowdown reduced by 30%, Turbo Start, speed +4 km/h, boost duration +0.7 seconds.',
 '더피의 세트파츠를 모두 모으면 20% 충돌 감소 효과 + 4km/h 속도 증가 + 부스트 사용시간 0.5초 증가':'Equip the complete Duffy set: collision slowdown reduced by 20%, speed +4 km/h, boost duration +0.5 seconds.',
 '에리나의 세트파츠를 모두 모으면 부스터의 기본 충전 속도가 50% 증가 + 얻는 경험치 2% 증가 + 파츠 드랍율 5% 증가':'Equip the complete Erina set: base boost recharge rate +50%, EXP gained +2%, part drop rate +5%.',
 '유키의 세트파츠를 모두 모으면 충돌 포인트 75P 증가 + 가속 포인트 75P 증가 + 체이싱 데미지 12% 증가':'Equip the complete Yuki set: durability +75 points, acceleration +75 points, chase damage +12%.',
 '카일라의 세트파츠 4개를 모두 모으면 충돌 포인트 50P 증가 + 가속 포인트 50P 증가 + 체이싱 데미지 10% 증가':'Equip all 4 Kayla set parts: durability +50 points, acceleration +50 points, chase damage +10%.',
 '혜영의 세트파츠 4개를 모두 모으면 출발 부스터 + 얻는 경험치 1% 증가 + 파츠 드랍율 4% 증가':'Equip all 4 Hyeyoung set parts: Turbo Start, EXP gained +1%, part drop rate +4%.',
}

# Long phrases precede shorter terms, so a translated compound keeps its actual meaning.
TERMS = {
 '고품격 레시피':'Premium recipe','평범한 레시피':'Standard recipe',
 '자동차 구매 축하':'Car purchase reward','의뢰소 이동 축하':'Station transfer reward',
 '레벨 달성 축하':'Level achievement reward','색칠성공':'Successful coloring',
 '고품격':'Premium','평범한':'Standard','초콜릿':'Chocolate','달걀바구니':'Egg Basket',
 '반짝반짝':'Sparkling','알록달록':'Colorful','화려한':'Brilliant','고광택':'High Gloss',
 '물감을 사용했을 경우':'when using paint','색칠':'Coloring','성공':'Success',
 '내가먹기 사용 시':'when consumed by yourself','사용했을 경우':'when used',
 '사용시':'on use','사용 시':'on use','사용':'Use','레벨':'Level',
 '보상등급':'Reward tier','단계에서':'at stage','보상그룹':'Reward group',
 '변형확률증가용액':'Conversion Chance Solution','변형확률':'Conversion chance',
 '변형용액':'Conversion Solution','옵션 파츠':'Option Parts','변형':'Conversion',
 '강화제':'Enhancer','강화':'Enhancement','패키지':'Package','연습용':'Practice',
 '엽습용':'Practice','옵션':'Option','타입':'Type','자동차':'Car',
 '가을대풍작이벤트':'Autumn Harvest Event','신선한 고기':'Fresh Meat','신선한 과일':'Fresh Fruit',
 '신선한 생선':'Fresh Fish','신선한 채소':'Fresh Vegetables','부활절':'Easter',
 '캐릭터뱃지':'Character Badge','캐릭터 뱃지':'Character Badge','캐릭터':'Character','뱃지':'Badge',
 '패시브어시스트':'Passive Assist','패시브':'Passive','어시스트':'Assist','캡슐상품아이템':'Capsule prize item',
 '가챠상품아이템':'Gotcha prize item','차량가챠':'Car Gotcha','차량캡슐':'Car Capsule',
 '캡슐':'Capsule','가챠':'Gotcha','차량':'Car','아이템':'Item','상품':'Product',
 '획득':'Acquired','확률':'Chance','세트':'Set','셋':'Set','캐쉬':'G Coin','미확인':'Unidentified',
 '일반':'Regular','꽝':'No prize','섬머페스트벌':'Summer Festival','리워드':'Reward',
 '에어인테이크':'Air Intake','에어덕트':'Air Duct','데칼':'Decal','선팅':'Window Tint',
 '그린':'Green','다크':'Dark','블루':'Blue','골드':'Gold','레드':'Red','핑크':'Pink',
 '브라운':'Brown','그레이':'Gray','바이올렛':'Violet','사파이어':'Sapphire','실버':'Silver',
 '오렌지':'Orange','일렉트릭':'Electric','카본':'Carbon','페인트':'Paint','옐로':'Yellow',
 '네온':'Neon','플러스':'Plus','디럭스':'Deluxe','베타':'Beta','알파':'Alpha','더블':'Double',
 '골드윙':'Goldwing','데빌':'Devil','디미누엔노':'Diminuendo','미트렌':'Mitren','세이버':'Saber',
 '이니그마':'Enigma','티나':'Tina','플라즈마':'Plasma','박서':'Boxer','비바체':'Vivace',
 '커세어':'Corsair','스몰':'Small','에밀':'Emil','메가':'Mega','슈발베':'Schwalbe',
 '스펙터':'Specter','파세오':'Paseo','가고일':'Gargoyle','볼크':'Volk','코러스':'Chorus',
 '템플라':'Templar','시그마':'Sigma','크레센도':'Crescendo','그라비티':'Gravity',
 '디아블로':'Diablo','프레스토':'Presto','버닝':'Burning','라이트닝':'Lightning',
 '잭 오 랜턴':'Jack-o-Lantern','라인볼':'Line Ball','배틀존':'Battle Zone','미션배틀':'Mission Battle',
 '배틀':'Battle','미션':'Mission','요원의':'Agent','비밀':'Secret','특수':'Special',
 '재활용':'Recycled','얼음':'Ice','에어로':'Aero','상품권':'Voucher','슬롯':'Slot','익스펜더':'Expander',
 '파이어':'Fire','오버드라이브':'Overdrive','디텍쳐':'Detector','박스':'Box','시드':'Seed',
 '드링크':'Drink','인형':'Doll','구성품':'Contents','요리사의':'Chef','레스토랑에':'to the restaurant',
 '위장키트':'Camouflage Kit','연료':'Fuel','제조킷':'Crafting Kit','향상제':'Improver',
 '납품':'Delivery','엔진':'Engine','가루':'Powder','튜닝':'Tuning','불법':'Illegal','면세용':'Duty-free',
 '마피아의':'Mafia','폭죽':'Fireworks','바쿠스':'Bacchus','묶음':'Bundle','결정':'Crystal',
 '활성':'Active','골드바':'Gold Bar','인트로':'Intro','고급':'High-grade','워프':'Warp',
 '깃발체크라인':'Flag Check Line','주고받기':'Exchange','불':'Fire','평가':'Rating',
 '긴급발동':'Emergency Activation','긴급':'Emergency','발동':'Activation',
 '보디 가드':'Bodyguard','버닝 업':'Burning Up','하이':'High',
 '정성':'Careful','반짝':'Sparkle','물감':'Paint','쿠폰':'Coupon','알파벳':'Letter',
 '상급':'High-grade','보호제':'Protectant','급속수리':'Quick Repair',
 '스폐셜':'Special','신비한':'Mysterious','중품':'Medium-grade','하품':'Low-grade',
 '모든 능력치':'All stats','차체':'Car body','투라인':'Two-Line','루프':'Roof',
 '하드':'Hard','이지':'Easy','베리':'Very','위성레이저':'Satellite Laser','유도미사일':'Homing Missile',
 '터렛':'Turret','해병':'Marine','유저':'Player','난이도':'Difficulty','게틀링':'Gatling',
 '직사화기':'Direct-Fire Weapon','시한폭발':'Timed Explosion','에로우':'Arrow','스톰':'Storm',
 '근접광역':'Close-range area effect','광역':'Area effect','플라즈마건':'Plasma Gun',
 '로드할 파일은 필요없음':'No file needs to be loaded','미사일':'Missile','유도':'Homing',
 '가속형':'Acceleration type','속도형':'Speed type',
 '단계':'Stage','용액':'Solution','그룹':'Group','레시피':'Recipe','윙':'Wing',
 '당첨':'Winning prize','신차':'New car','결과':'Result','언더시티':'Undercity','이벤트':'Event',
 '달걀':'Egg','데미지':'Damage','업':'Up','특별':'Special','라인':'Line','미트로':'Mitro',
 '제이슨':'Jason','지희':'Jihee','리비아':'Livia','민영':'Minyoung','지니':'Jinny',
 '무적질주':'Invincible Rush','스키드러쉬':'Skid Rush','키트':'Kit','실패':'Failure','평판':'Reputation',
 '파워업':'Power-up','드립':'Drip','시스템':'System','대형':'Large',
 '개수':'Count','매카와치':'Mecha Watch','펄스쉴드':'Pulse Shield','필드퀵슬롯':'Field quick slot',
 '수리걸':'Repair Girl','폭주':'Rampage','리틀':'Little','신덴':'Shinden','미들':'Middle',
 '식스':'Six','팬텀':'Phantom','포르테':'Forte','드리프트':'Drift','크리티컬':'Critical',
 '드랍':'Drop','휴대용':'Portable','한정':'Limited','산타의':'Santa\'s',
 '기간':'Time-based','종량':'Usage-based','기타':'Other',
 '픽업':'Pickup','승합':'Van','호위':'Escort','파티순찰 클리어':'Party Patrol completions',
 '충돌 수 3이하 50%':'50% for 3 or fewer collisions','3분 30초 이하 30%':'30% for 3 minutes 30 seconds or less',
 '라인볼 포인트':'Line Ball points','라이볼 포인트 150이상 30%':'30% for 150 or more Line Ball points',
 '배틀보상':'Battle reward','체이싱보상':'Chase reward','등장HUV수':'Spawned HUV count',
 '세트파츠 렌트 시 : : :':'Rental set bonus:', '충돌 시 줄어드는 속도':'Collision speed loss',
 '체이싱 시 크리티컬 충돌 확률':'Chase critical hit chance', '부스터 사용시간':'Boost duration',
 '부스트 사용시간':'Boost duration', '파츠 드랍 확률':'Part drop chance', '파츠 드랍율':'Part drop rate',
 '얻는 경험치':'EXP gained', '속도증가':'Speed increase', '속도 증가':'Speed increase',
 '터보 스타트':'Turbo Start', '급정거':'Quick Stop',
 '미트론 크리스탈 스킬북':'Mittron Crystal Skill Book','미트론 강화제':'Mittron Enhancer',
 '네오 미확인 스킬북':'Unidentified Neo Skill Book','파츠 열처리 키트':'Parts Heat Treatment Kit',
 '파츠 스킬북':'Parts Skill Book','파츠 부속품':'Part Component','파츠 가루 U':'Ultra Parts Powder',
 '울트라 파츠 가루':'Ultra Parts Powder','미완성':'Incomplete',
 '울트라':'Ultra','개인 수리 키트':'Personal Repair Kit','파티 수리 키트':'Party Repair Kit',
 '네오 무기 수리':'Neo Weapon Repair','네오 무기 슬롯':'Neo Weapon Slot',
 '방어 장갑 수리':'Armor Repair','융합기 수리':'Fusion Unit Repair','증폭기 수리':'Amplifier Repair',
 '수리 캡슐':'Repair Capsule','부스터 충전기':'Boost Charger','부활 아이템':'Revival Item',
 '공격력 상승':'Attack Up','방어력 상승':'Defense Up','교란 섬광탄':'Disruption Flashbang',
 '언더시티 다이렉트':'Undercity Direct','마일리지':'Mileage', '크리스탈 해골':'Crystal Skull',
 '인디의 중절모':'Indy\'s Fedora','인디의 채찍':'Indy\'s Whip','인디아나 존스4':'Indiana Jones 4',
 '서울모터쇼응모권':'Seoul Motor Show Entry Ticket','택시4 영화티켓':'Taxi 4 Movie Ticket',
 '피자헛 15% 할인 쿠폰':'Pizza Hut 15% Discount Coupon','피자헛 공짜 피자 쿠폰':'Pizza Hut Free Pizza Coupon',
 '해피빈 콩':'Happybean Bean','여름 이벤트 응모권':'Summer Event Entry Ticket',
 '이벤트 응모권 조각':'Event Entry Ticket Piece','이벤트 응모권':'Event Entry Ticket',
 '응모권':'Entry Ticket','스킬북':'Skill Book','파츠':'Parts',
 '렌터카':'Rental Car','노멀':'Normal','노말':'Normal','슈퍼':'Super','하이퍼':'Hyper',
 '스피드':'Speed','기본':'Basic','가속':'Acceleration','부스트':'Boost','부스터':'Boost',
 '속도':'Speed','충돌':'Durability','렌트':'Rental', 'S PC방전용':'S PC Cafe Exclusive',
 '남자':'Male','여자':'Female','트래픽카':'Traffic cars','전용차':'Personal Car',
 '브랜튼':'Branton','카일라':'Kayla','혜영':'Hyeyoung','에리나':'Erina','더피':'Duffy','유키':'Yuki','얀':'Yahn',
 '엠블란스':'Ambulance','견인차':'Tow Truck','포겔빵집':'Fogel Bakery','大탑차':'Large Box Truck',
 '大포장':'Large Covered Truck','탑차':'Box Truck','포장':'Covered Truck','용달':'Delivery Truck',
 'NHN 택배':'NHN Courier','트레일러':'Trailer','탱크로리':'Tanker','경차':'Compact Car',
 '승용차':'Passenger Car','픽업트럭':'Pickup Truck','승합차':'Van','점프카':'Jump Car',
 '택시':'Taxi','순찰차':'Patrol Car','시티버스':'City Bus','시내 버스':'City Bus','청소차':'Street Sweeper',
 '우체국':'Post Office','활어차':'Live Fish Truck','분뇨차':'Septic Truck','카지노광고':'Casino Advertisement',
 '덤프트럭':'Dump Truck','레미콘':'Concrete Mixer','소방차':'Fire Engine','콘도버스':'Resort Bus',
 '콘도 버스':'Resort Bus','사이프러스':'Cypress','목재운반':'Logging','산불관리':'Wildfire Patrol',
 '스포츠센터버스':'Sports Center Bus','스포츠센터 버스':'Sports Center Bus','방송국':'Broadcasting Station',
 '소형':'Small','마트':'Mart','배달':'Delivery','OMD 대법원 호송버스':'OMD Supreme Court Transport Bus',
 '교통관리국':'Traffic Authority','오로스 경찰본부':'Oros Police Headquarters','오로스':'Oros',
 '의문의':'Mysterious','2층 버스':'Double-Decker Bus','대만':'Taiwan','왕룽':'Wang Long',
 '다치코마':'Tachikoma','양면머신':'Double-Sided Machine','호버머신':'Hover Machine','전차':'Tank',
 'AI 채팅':'AI chat','2배방 등장 비율':'2X room spawn rate','3배방 등장 비율':'3X room spawn rate',
 '4배방 등장 비율':'4X room spawn rate','6배방 등장 비율':'6X room spawn rate','8배방 등장 비율':'8X room spawn rate',
 '문팰리스':'Moon Palace','문펠리스':'Moon Palace','문팰리스트랙':'Moon Palace track',
 '코이노니아':'Koinonia','크라스':'Cras','미트로 시티':'Mitro City','미트론':'Mittron',
 '공장지역':'Factory District','채굴단지':'Mining Complex','목재가공단지':'Lumber Processing Complex',
 '보도블럭':'Pavement','상징탑':'Landmark Tower','전력 발전소':'Power Plant','풍차':'Windmill',
 '관측소':'Observatory','항구':'Harbor','바닷물':'Seawater','백사장':'Beach','산악지역':'Mountain Area',
 '콘서트 홀':'Concert Hall','키퍼터널':'Keeper Tunnel','폭포':'Waterfall','해안':'Coast',
 '프라우 터널':'Frau Tunnel','미토스 터널':'Mitos Tunnel','철재도로':'Steel Road',
 '골드윙비행장':'Goldwing Airfield','키즈월드':'Kids World',
 '퀘스트 클리어':'Quest completion','퀘스트용':'Quest version','퀘스트':'Quest',
 '추격 AI':'Chase AI','개틀링':'Gatling','다연장포':'Multiple Rocket Launcher','로켓런쳐':'Rocket Launcher',
 '유도탄':'Homing Missile','정예':'Elite','철갑건':'Armor-Piercing Gun','철갑탄':'Armor-Piercing Round',
 '체인건':'Chaingun','충돌형':'Ram Type','무기':'Weapon','네오':'Neo',
 '상자':'Box','키 파츠':'Key Parts','선물':'Gift','경험치':'EXP','미토':'Mito','포인트':'Points',
 '개조':'Upgrade','차량개조':'Car Upgrade','도킹':'Docking','조합':'Combine','보상':'Reward',
 '증가':'increase','감소':'reduction','시간':'time','사용 불가':'disabled',
 '무기 사용시 부스터 게이지 소모량 감소':'Weapon boost gauge cost reduction',
 '무기데미지의 일정량을 부스터 게이지로 전환':'Weapon damage converted to boost gauge',
 '무기데미지의 일정량을 HP로 전환':'Weapon damage converted to HP',
 '피해 데미지의 부스터 게이지로 전환':'Received damage converted to boost gauge',
 '받는 모든 데미지':'All damage received','받는 무기 데미지':'Weapon damage received',
 '받는 충돌 데미지':'Ram damage received','충돌 공격력':'Ram attack','모든 공격력':'All attack',
 '무기 공격력':'Weapon attack','무기 최대 공격력':'Maximum weapon attack',
 '무기 크리티컬 확률':'Weapon critical chance','무기 사거리':'Weapon range','무기 재충전 시간':'Weapon recharge time',
 '무기 데미지 피해':'Weapon damage taken','충돌 데미지 피해':'Ram damage taken',
 '부스터 게이지 완전 소모':'Fully drains the boost gauge','부스터 게이지 재충전 불가':'Boost gauge recharge disabled',
 '부스터 최대 게이지':'Maximum boost gauge','속도 감속':'Speed reduction','감속':'speed reduction',
 '드리프트 사용 불가':'Drifting disabled','아이템 장착 효과 해제':'Equipped item effect removed',
 '장갑 바디 패널(armor panel) 아이템 장착 효과 해제':'Equipped armor body panel effect removed',
 '찬스 200%( S PC방 패키지 옵션)':'Chance 200% (S PC Cafe package option)',
 '방어력(SHP)':'Defense (SHP)','감소 효과':'reduction effect','효과':'effect','피해':'damage',
 '가을 대풍작':'Autumn Harvest','대풍작물류센터':'Harvest Logistics Center',
 '퀵서비스':'Delivery','파티순찰':'Party Patrol','순찰 클리어':'Patrol completions','순찰':'Patrol',
 '주행거리':'Driving distance','금메달':'Gold medals','은메달':'Silver medals','동메달':'Bronze medals',
 '싱글 배틀 횟수':'Solo battle count','팀 배틀 횟수':'Team battle count',
 'HUV 뒤가 아닌 부위 타격':'HUV hits outside the rear','HUV 드리프트 타격':'Drift hits on HUVs',
 'HUV 부스터 타격':'Boost hits on HUVs','HUV 크리티컬 타격':'Critical hits on HUVs',
 'HUV 사냥 마리 수':'HUVs caught','의뢰소':'Station','도시':'City',
 '모터쇼시작':'Motor Show start','모터쇼이벤트':'Motor Show event','피자헛이벤트':'Pizza Hut event',
 '해피빈이벤트':'Happybean event','꽃':'Flower','시작':'Start','도착':'Arrival','출발':'Departure',
 '오로스 화살표':'Oros Arrow','화살표':'Arrow','리버스':'Reverse',
 '레일건':'Railgun','마인':'Mine','웨이브':'Wave','캐논':'Cannon','홍빠오':'Red Envelope',
}


def english(text):
    """Display-only translation. English text, IDs and empty cells pass through verbatim."""
    if not HANGUL.search(text):
        return text
    return _english(text)


@lru_cache(maxsize=16384)
def _english(text):
    normalized=re.sub(r'\s+',' ',text.strip().strip('"')).strip()
    if normalized in EXACT:
        return EXACT[normalized]
    # Full sentence templates avoid changing quantities or reversing effect meanings.
    m=re.fullmatch(r'사용 즉시 (모든 파티원의 )?(\d+) 내구력 회복 - 재사용 대기시간 (\d+)초\s*\(필드 퀵슬롯 아이템\)',normalized)
    if m:
        party,amount,seconds=m.groups()
        return f'Instantly restores {amount} durability'+(' to all party members' if party else '')+f'. Cooldown: {seconds} seconds. Field quick-slot item.'
    m=re.fullmatch(r'사용 즉시 (\d+)초 동안 (무기 공격력|방어력) 포인트가 (\d+) 포인트 상승 - 재사용 대기시간 (\d+)초\s*\(필드 퀵슬롯 아이템\)',normalized)
    if m:
        seconds,kind,amount,cooldown=m.groups()
        return f'{"Weapon attack" if kind=="무기 공격력" else "Defense"} +{amount} points for {seconds} seconds. Cooldown: {cooldown} seconds. Field quick-slot item.'
    m=re.fullmatch(r'마우스 우 클릭 시 현재 장착 중인 (방어 장갑|융합기|증폭기|플라즈마 무기)의 내구도를 (\d+) 수리해 준다\.',normalized)
    if m:
        kind,amount=m.groups()
        kind={'방어 장갑':'armor','융합기':'fusion unit','증폭기':'amplifier','플라즈마 무기':'plasma weapon'}[kind]
        return f'Right-click to restore {amount} durability to the equipped {kind}.'
    m=re.fullmatch(r'사용시 부스터 게이지 (\d+) 충전 \(플라즈마 무기 기준\)',normalized)
    if m: return f'Restores {m[1]} boost gauge (for plasma weapons).'
    m=re.fullmatch(r'자신의 레벨을 (\d+)으로 다운 시켜준다\.',normalized)
    if m: return f'Reduces your level to {m[1]}.'
    m=re.fullmatch(r'유통기한이 끝난 미완성 (가속|부스트|속도|충돌)파츠',normalized)
    if m: return f'Expired Incomplete {english(m[1])} Part'
    m=re.fullmatch(r'(10개를 모으면 |미트론 강화제 PLUS를 이용해 )(?:미트론 강화제 PLUS를 이용해 )?울트라 (가속|부스트|속도|충돌)파츠로 만들 수 있다\.(.*)',normalized)
    if m:
        first,kind,tail=m.groups()
        return (('Collect 10 and use' if first.startswith('10') else 'Use')+f' Mittron Enhancer PLUS to make an Ultra {english(kind)} Part.'+(' Available after Neo City officially opens.' if tail else ''))
    m=re.fullmatch(r'(.+?)(?:를|을) 만들 수 있는 스킬북입니다\. \(마우스 우클릭으로 스킬을 배울 수 있습니다\.?\)',normalized)
    if m: return f'A skill book for crafting {english(m[1])}. Right-click to learn the skill.'
    m=re.fullmatch(r'파츠 가루 U 를 이용하여 미트론 크리스탈을 만들 수 있는 스킬북입니다\. \(마우스 우클릭으로 스킬을 배울 수 있습니다\)',normalized)
    if m: return 'A skill book for crafting Mittron Crystal from Ultra Parts Powder. Right-click to learn the skill.'
    m=re.fullmatch(r'\[현재한국전용\]알파벳 ([A-Z])\. 모든 조각을 모으면 하나의 단어가 완성되어, 이벤트 응모권이 됩니다\.',normalized)
    if m: return f'[Korea only] Letter {m[1]}. Collect every letter to complete the word and obtain an event entry ticket.'
    result=normalized
    # Numeric suffixes used by upgrade requirements and table headings.
    result=re.sub(r'(\d+)도시',r'City \1',result)
    result=re.sub(r'(\d+)차도시',r'City \1',result)
    result=re.sub(r'(\d+)의뢰소',r'Station \1',result)
    result=re.sub(r'(\d+)배방 등장 비율',r'\1X room spawn rate',result)
    result=re.sub(r'보기(\d+)',r'Answer choice \1',result)
    result=re.sub(r'(\d+)회 이상',r'at least \1 times',result)
    result=re.sub(r'(\d+)개 이상',r'at least \1',result)
    result=re.sub(r'(\d+)마리 이상',r'at least \1',result)
    result=re.sub(r'(\d+)km 이상',r'at least \1 km',result)
    result=re.sub(r'(\d+)회',r'\1 attempts',result)
    result=re.sub(r'(\d+)배',r'\1x',result)
    result=re.sub(r'(\d+)개',r'\1 units',result)
    result=re.sub(r'(\d+)등',r'place \1',result)
    result=re.sub(r'(\d+)일',r'\1 days',result)
    result=re.sub(r'(\d+(?:\.\d+)?)초',r'\1 seconds',result)
    for source,target in sorted(TERMS.items(),key=lambda p:len(p[0]),reverse=True):
        result=result.replace(source,' '+target+' ')
    # Standalone particles only: replacing a syllable inside a proper name corrupts it.
    for source,target in {'및':'and','이상':'or more','때':'when','시':'when','만':'only','용':'version'}.items():
        result=re.sub(r'(?<![가-힣])'+source+r'(?![가-힣])',target,result)
    return re.sub(r'\s+',' ',result).strip()
