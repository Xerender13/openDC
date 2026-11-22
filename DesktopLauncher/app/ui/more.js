'use strict';
/* The seven More windows on the server's own tables (helper odc_more.py): Community, Ranking, Coupon Book, Licenses,
   Production Skill Book, Drift Shop and Gotcha. Viewing works with the game open; a change needs the game closed.
   Uses app.js / panels.js globals: T, t, esc, $, $$, ICONS, loadIcons, errText, Tip, MORE_PAGES. */
(function () {
  const X = {
    pt: {
      mSubCom: 'Amigos, bloqueados e mensagens (Communication Zone).', mSubRank: 'Ranking do mês e das crews.', mSubCp: 'Cupons de carro: complete o requisito e troque na concessionária.',
      mSubLic: 'Licenças do corredor e o dinheiro de posse do mês.', mSubSk: 'Livros de fabricação aprendidos e o nível de fabricação.', mSubShop: 'Itens visuais e de tuning para o carro escolhido.', mSubGot: 'Cápsulas de carro por CC ou Mito.',
      cFriends: 'Lista de amigos', cAdd: 'Adicionar', cDel: 'Remover', cBlocks: 'Lista de bloqueio', cBlock: 'Bloquear', cUnblock: 'Desbloquear', cInbox: 'Caixa de entrada', cSaved: 'Salvas', cNew: 'Nova mensagem',
      cName: 'Nome do corredor', cLevel: 'Nível', cNameCol: 'Nome', cCrew: 'Crew', cWhere: 'Local', cOnline: 'online', cOffline: 'offline', cAsked: 'pedido enviado', cAsking: 'quer ser seu amigo', cAccept: 'Aceitar',
      cFrom: 'De', cText: 'Mensagem', cDate: 'Data', cSend: 'Enviar', cKeep: 'Salvar', cDelMsg: 'Apagar', cTo: 'Para', cNone: 'Nada aqui.', cNeedName: 'Escreva o nome do corredor embaixo.', cDone: '✓ Feito ({n}).', cSent: '✓ Mensagem enviada para {n}.', cNewMsg: 'nova',
      rGame: 'Jogo', rCrews: 'Crews', rReset: 'O ranking do mês zera no dia 1º às 00:00.', rPos: 'Posição', rRec: 'Recorde', rLast: 'Mês passado', rCar: 'Carro em uso', rNone: 'Sem ranking', rDetail: 'Detail', rTop: 'Top 10',
      rCats: { exp: 'Experiência', km: 'Distância', make: 'Fabricação', ss: 'SS Battle', mission: 'Missões', gs: 'GS Battle', huv: 'HUV destruídos', gt: 'GT Championship', neohuv: 'NeoHUV destruídos', mvp: 'MVP batalha de canal' },
      rUnits: { exp: 'Exp', km: 'Km', make: 'qtd', ss: 'pts', mission: 'qtd', gs: 'pts', huv: 'qtd', gt: 'pts', neohuv: 'qtd', mvp: 'pts' },
      rTeam: 'Crew', rMaster: 'Líder', rMembers: 'Membros', rPoints: 'Pontos', rWins: 'Vitórias', rCreated: 'Criada', rNoCrew: 'Nenhuma crew no servidor ainda.',
      cpMinutes: 'minutos', cpTimes: 'vezes', cpPrice: 'Preço de compra', cpReqT: 'Requisito', cpReqLine: '{r} ({n} {u})', cpLevel: 'Nível necessário', cpLvl: 'Lv. ({n}) ou mais', cpSpeed: 'Velocidade', cpAccel: 'Aceleração', cpDura: 'Resistência', cpBoost: 'Boost', cpReqLong: ['Vitórias na Battle Zone', 'Entregas feitas', 'Perseguições vencidas', 'Combos feitos', 'Tempo dirigindo', 'Drifts feitos', 'Skill Pass feitos', 'Saltos feitos', 'Tempo na contramão', 'Modos de jogo concluídos', 'Quest concluída'],
      cpReq: ['Battle Zone', 'Delivery', 'Chase', 'Combo', 'Driving Time', 'Drift', 'Skill Pass', 'Jump', 'Reckless', 'GameMode', 'Quest'], cpNeed: '[ Requisito ]', cpNow: '[ Agora ]', cpNot: 'Ainda não completou', cpReady: '★ Cupom pronto: troque na concessionária.', cpTaken: '✓ Cupom já recebido.',
      cpCoupon: '★ Cupom', cpHelp: '1. Ganhe o cupom completando o requisito. 2. Troque na concessionária do Battledome.', cpGive: 'Dar o cupom (GM)', cpGiven: '✓ Cupom {n} entregue no inventário.', cpMin: 'min',
      lMoney: 'Dinheiro de posse das licenças:', lCount: '{n} de {m} licenças', lHas: '✓ Tem esta licença', lHasnt: 'Não tem esta licença', lEffect: 'Efeito', lCond: 'Como ganhar', lGive: 'Dar a licença (GM)', lTake: 'Tirar a licença (GM)', lHelp: 'O dinheiro de posse zera todo dia 1º; o valor depende das licenças que o corredor tem.',
      skLevel: 'Nível de fabricação', skGroups: { low: 'Habilidade baixa', med: 'Habilidade média', high: 'Habilidade alta', 'very high': 'Habilidade máxima', level: 'Habilidade de nível' }, skHelp: 'O nível sobe com a experiência de fabricar itens dos livros.',
      skLearned: '✓ Aprendido', skNot: 'Não aprendido', skReq: 'Nível de fabricação {n}', skMats: 'Materiais', skMakes: 'Fabrica', skLearn: 'Ensinar (GM)', skForget: 'Esquecer (GM)',
      dsFull: 'Só o carro (tela cheia)', dsScene: 'Trocar cenário: loja / garagem', dsHomeHint: 'Escolha Visual, Tuning ou Outros para ver os itens que servem neste carro.', dsSelList: 'Seleção', dsBuyAll: 'Comprar itens equipados', dsDefault: 'Padrão', dsCategory: 'Categoria', dsPurchase: 'Comprar', dsCheckout: 'Finalizar compra', dsPeriod: 'Período', dsDays: '{n} dias', dsForever: 'Permanente', dsTotal: 'Total:', dsSubs: { AERO: 'Aero', AERO_ADV: 'Aero', BOOSTER: 'Booster', TIREWHEEL: 'Pneus / Rodas', AEROWING: 'Aero Wing', BOOSTERWING: 'Booster Wing', 'Air Duct': 'Air Duct', TIRE: 'Pneu', GLOSSTIRE: 'Pneu brilhante', SPOILER: 'Spoiler', CARREMODELING: 'Modificar carro', PAINT: 'Pintura', PAINTHIGHGLOSS: 'Pintura', UNDERNEON: 'Neon', WINDOWTINTING: 'Vidro', DECAL: 'Decal', NUMBERPLATE: 'Placa', SOUND: 'Som', STICKERLICENSE: 'Adesivo' }, ctlTitle: 'Carro', ctlLeft: 'Seta esquerda', ctlRight: 'Seta direita', ctlHazard: 'Pisca-alerta', ctlBrake: 'Luz de freio', ctlHead: 'Faróis', ctlSteer: 'Virar as rodas (até 65°; duplo clique centraliza)', ctlFold: 'Mostrar / esconder os controles', ctlAuto: 'Girar sozinho',
      shHome: 'HOME', shVisual: 'Dress-Up', shTuning: 'Tuning', shOther: 'Misc.', shAll: 'Todos', shHomeT: 'Os itens comprados ficam na aba Drift Item do inventário (os de uso imediato não).\nItens do Drift Shop não podem ser revendidos nem ir para o leilão.\nAqui o launcher compra para o corredor escolhido, com o Mito ou o CC dele.',
      shMito: 'Mito disponível', shCC: 'CC disponível', shBuy: 'Comprar', shCar: 'Carro', shPeriod: 'Período', shBought: '✓ Comprado: {n}.', shExtended: '✓ Prazo somado: {n}.', shForGood: 'para sempre', shDays: '{n} dias', shPick: 'Escolha um item.', shBonus: 'Bônus', shOnCar: 'vai direto no carro escolhido', shSearch: 'Procurar',
      shStats: ['Velocidade', 'Aceleração', 'Choque', 'Boost'], shGrade: 'Desempenho do carro (V1-V9)',
      gSelCC: 'Escolher CC', gSelMito: 'Escolher Mito', gMyCC: 'Meu CC', gMyMito: 'Meu Mito', gCostCC: 'Custo CC Gotcha (x1)', gCostMito: 'Custo Mito Gotcha (x1)', gChances: 'Chance de sair:', gCongrats: 'Parabéns, você ganhou:', gBoxNote: 'A caixa do carro foi para o inventário. Abra a caixa e o carro entra numa vaga da garagem.', gPointsNote: 'Os Capsule Points foram para o inventário.',
      gTitle: 'DRIFTCITY GOTCHA', gCC: 'CC Gotcha', gMito: 'Mito Gotcha', gSpin: 'Girar para {n}', gWon: 'Você ganhou', gPoints: '10 Capsule Points', gSlot: 'Slot {n}', gHint: 'Cada giro dá um carro dos slots (caixa de presente V1) ou 10 Capsule Points. Abra a caixa no jogo.',
      err3: { no_runner: 'Corredor não encontrado.', already_friend: 'Já é amigo.', msg_blocked: 'Esse corredor bloqueou você.', no_item: 'Item não encontrado.', coupon_taken: 'Esse cupom já foi recebido.', shop_price: 'Esse preço não existe mais.', no_cc: 'Não tem CC suficiente.', gotcha_off: 'A Gotcha não existe nesse servidor.' },
    },
    en: {
      mSubCom: 'Friends, blocked and messages (Communication Zone).', mSubRank: 'Monthly and crew ranking.', mSubCp: 'Car coupons: meet the requirement and trade it at the dealer.',
      mSubLic: "The character's licenses and this month's holding money.", mSubSk: 'Learned production books and the production level.', mSubShop: 'Visual and tuning items for the chosen car.', mSubGot: 'Car capsules for CC or Mito.',
      cFriends: 'Friend list', cAdd: 'Add', cDel: 'Remove', cBlocks: 'Block list', cBlock: 'Block', cUnblock: 'Unblock', cInbox: 'Inbox', cSaved: 'Saved', cNew: 'New message',
      cName: 'Character name', cLevel: 'Level', cNameCol: 'Name', cCrew: 'Crew', cWhere: 'Where', cOnline: 'online', cOffline: 'offline', cAsked: 'request sent', cAsking: 'wants to be your friend', cAccept: 'Accept',
      cFrom: 'From', cText: 'Message', cDate: 'Date', cSend: 'Send', cKeep: 'Save', cDelMsg: 'Delete', cTo: 'To', cNone: 'Nothing here.', cNeedName: 'Type the character name below.', cDone: '✓ Done ({n}).', cSent: '✓ Message sent to {n}.', cNewMsg: 'new',
      rGame: 'Game', rCrews: 'Crews', rReset: 'The monthly ranking resets on the 1st at 00:00.', rPos: 'Position', rRec: 'Record', rLast: 'Last month', rCar: 'Car in use', rNone: 'Not ranked', rDetail: 'Detail', rTop: 'Top 10',
      rCats: { exp: 'Experience', km: 'Distance', make: 'Production', ss: 'SS Battle', mission: 'Missions', gs: 'GS Battle', huv: 'HUV destroyed', gt: 'GT Championship', neohuv: 'NeoHUV destroyed', mvp: 'Channel battle MVP' },
      rUnits: { exp: 'Exp', km: 'Km', make: 'qty', ss: 'pts', mission: 'qty', gs: 'pts', huv: 'qty', gt: 'pts', neohuv: 'qty', mvp: 'pts' },
      rTeam: 'Crew', rMaster: 'Leader', rMembers: 'Members', rPoints: 'Points', rWins: 'Wins', rCreated: 'Created', rNoCrew: 'No crew on the server yet.',
      cpMinutes: 'minutes', cpTimes: 'times', cpPrice: 'Purchase price', cpReqT: 'Requirements', cpReqLine: '{r} ({n} {u})', cpLevel: 'Necessary level', cpLvl: 'Lv. ({n}) or higher', cpSpeed: 'Speed', cpAccel: 'Accel.', cpDura: 'Dura.', cpBoost: 'Boost', cpReqLong: ['Battle Zone wins', 'Deliveries made', 'Chases won', 'Combos performed', 'Driving time', 'Number of drifts performed', 'Skill passes made', 'Jumps made', 'Reckless driving time', 'Game modes completed', 'Quest cleared'],
      cpReq: ['Battle Zone', 'Delivery', 'Chase', 'Combo', 'Driving Time', 'Drift', 'Skill Pass', 'Jump', 'Reckless', 'GameMode', 'Quest'], cpNeed: '[ Requirement ]', cpNow: '[ Now ]', cpNot: 'Not completed yet', cpReady: '★ Coupon ready: trade it at the dealer.', cpTaken: '✓ Coupon already received.',
      cpCoupon: '★ Coupon', cpHelp: '1. Earn the coupon by meeting the requirement. 2. Trade it at the Battledome dealer.', cpGive: 'Give the coupon (GM)', cpGiven: '✓ Coupon {n} put in the inventory.', cpMin: 'min',
      lMoney: 'License holding money:', lCount: '{n} of {m} licenses', lHas: '✓ Has this license', lHasnt: "Doesn't have this license", lEffect: 'Effect', lCond: 'How to get it', lGive: 'Give the license (GM)', lTake: 'Take the license (GM)', lHelp: 'Holding money resets on the 1st of every month; the amount depends on the licenses held.',
      skLevel: 'Production level', skGroups: { low: 'Low skill', med: 'Medium skill', high: 'High skill', 'very high': 'Top skill', level: 'Level skill' }, skHelp: 'The level rises with the experience of making items from the books.',
      skLearned: '✓ Learned', skNot: 'Not learned', skReq: 'Production level {n}', skMats: 'Materials', skMakes: 'Makes', skLearn: 'Teach (GM)', skForget: 'Forget (GM)',
      dsFull: 'Car only (full window)', dsScene: 'Switch backdrop: shop / garage', dsHomeHint: 'Pick Visual, Tuning or Others to see the items that fit this car.', dsSelList: 'Selection', dsBuyAll: 'Purchase equipped items', dsDefault: 'Default', dsCategory: 'Category', dsPurchase: 'Purchase', dsCheckout: 'Checkout', dsPeriod: 'Period', dsDays: '{n} days', dsForever: 'Permanent', dsTotal: 'Total:', dsSubs: { AERO: 'Aero', AERO_ADV: 'Aero', BOOSTER: 'Booster', TIREWHEEL: 'Tire Wheel', AEROWING: 'Aero Wing', BOOSTERWING: 'Booster Wing', 'Air Duct': 'Air Duct', TIRE: 'Tire', GLOSSTIRE: 'Glossy tire', SPOILER: 'Spoiler', CARREMODELING: 'Modify car', PAINT: 'Paint', PAINTHIGHGLOSS: 'Paint', UNDERNEON: 'Neon', WINDOWTINTING: 'Window', DECAL: 'Decal', NUMBERPLATE: 'Plate', SOUND: 'Sound', STICKERLICENSE: 'Sticker' }, ctlTitle: 'Car', ctlLeft: 'Left indicator', ctlRight: 'Right indicator', ctlHazard: 'Hazard lights', ctlBrake: 'Brake light', ctlHead: 'Head lights', ctlSteer: 'Turn the wheels (up to 65°; double-click centres)', ctlFold: 'Show / hide the controls', ctlAuto: 'Turn by itself',
      shHome: 'HOME', shVisual: 'Dress-Up', shTuning: 'Tuning', shOther: 'Misc.', shAll: 'All', shHomeT: "Bought items go to the inventory's Drift Item tab (instant-use ones don't).\nDrift Shop items can't be resold or put up for auction.\nHere the launcher buys for the chosen character, with their Mito or CC.",
      shMito: 'Mito available', shCC: 'CC available', shBuy: 'Buy', shCar: 'Car', shPeriod: 'Period', shBought: '✓ Bought: {n}.', shExtended: '✓ Time added: {n}.', shForGood: 'for good', shDays: '{n} days', shPick: 'Pick an item.', shBonus: 'Bonus', shOnCar: 'goes straight onto the chosen car', shSearch: 'Search',
      shStats: ['Speed', 'Accel', 'Crash', 'Boost'], shGrade: 'Car performance (V1-V9)',
      gSelCC: 'Select CC', gSelMito: 'Select Mito', gMyCC: 'My CC', gMyMito: 'My Mito', gCostCC: 'CC Gotcha cost (x1)', gCostMito: 'Mito Gotcha cost (x1)', gChances: 'Chance:', gCongrats: 'Congratulations, you won:', gBoxNote: 'The car box went to the inventory. Open it and the car takes a spot in the garage.', gPointsNote: 'The Capsule Points went to the inventory.',
      gTitle: 'DRIFTCITY GOTCHA', gCC: 'CC Gotcha', gMito: 'Mito Gotcha', gSpin: 'Spin for {n}', gWon: 'You won', gPoints: '10 Capsule Points', gSlot: 'Slot {n}', gHint: 'Each spin gives a slot car (V1 gift box) or 10 Capsule Points. Open the box in the game.',
      err3: { no_runner: 'Character not found.', already_friend: 'Already a friend.', msg_blocked: 'That character blocked you.', no_item: 'Item not found.', coupon_taken: 'That coupon was already received.', shop_price: 'That price no longer exists.', no_cc: 'Not enough CC.', gotcha_off: "This server has no Gotcha." },
    },
    ru: {
      mSubCom: 'Друзья, блокировки и сообщения (Communication Zone).', mSubRank: 'Рейтинг месяца и команд.', mSubCp: 'Купоны на машины: выполните условие и обменяйте у дилера.',
      mSubLic: 'Лицензии персонажа и деньги владения за месяц.', mSubSk: 'Изученные книги производства и уровень производства.', mSubShop: 'Визуальные и тюнинг-предметы для выбранной машины.', mSubGot: 'Капсулы с машинами за CC или Mito.',
      cFriends: 'Список друзей', cAdd: 'Добавить', cDel: 'Удалить', cBlocks: 'Чёрный список', cBlock: 'Заблокировать', cUnblock: 'Разблокировать', cInbox: 'Входящие', cSaved: 'Сохранённые', cNew: 'Новое сообщение',
      cName: 'Имя персонажа', cLevel: 'Уровень', cNameCol: 'Имя', cCrew: 'Команда', cWhere: 'Где', cOnline: 'в сети', cOffline: 'не в сети', cAsked: 'запрос отправлен', cAsking: 'хочет дружить', cAccept: 'Принять',
      cFrom: 'От', cText: 'Сообщение', cDate: 'Дата', cSend: 'Отправить', cKeep: 'Сохранить', cDelMsg: 'Удалить', cTo: 'Кому', cNone: 'Здесь пусто.', cNeedName: 'Введите имя персонажа внизу.', cDone: '✓ Готово ({n}).', cSent: '✓ Сообщение отправлено {n}.', cNewMsg: 'новое',
      rGame: 'Игра', rCrews: 'Команды', rReset: 'Рейтинг месяца обнуляется 1-го числа в 00:00.', rPos: 'Место', rRec: 'Рекорд', rLast: 'Прошлый месяц', rCar: 'Машина', rNone: 'Нет в рейтинге', rDetail: 'Detail', rTop: 'Топ 10',
      rCats: { exp: 'Опыт', km: 'Дистанция', make: 'Производство', ss: 'SS Battle', mission: 'Миссии', gs: 'GS Battle', huv: 'Уничтожено HUV', gt: 'GT Championship', neohuv: 'Уничтожено NeoHUV', mvp: 'MVP битвы каналов' },
      rUnits: { exp: 'Exp', km: 'Км', make: 'шт', ss: 'очк', mission: 'шт', gs: 'очк', huv: 'шт', gt: 'очк', neohuv: 'шт', mvp: 'очк' },
      rTeam: 'Команда', rMaster: 'Лидер', rMembers: 'Участники', rPoints: 'Очки', rWins: 'Победы', rCreated: 'Создана', rNoCrew: 'На сервере ещё нет команд.',
      cpMinutes: 'мин.', cpTimes: 'раз', cpPrice: 'Цена покупки', cpReqT: 'Условие', cpReqLine: '{r} ({n} {u})', cpLevel: 'Нужный уровень', cpLvl: 'Ур. ({n}) и выше', cpSpeed: 'Скорость', cpAccel: 'Ускор.', cpDura: 'Прочн.', cpBoost: 'Буст', cpReqLong: ['Победы в Battle Zone', 'Доставки', 'Выигранные погони', 'Комбо', 'Время вождения', 'Количество дрифтов', 'Skill Pass', 'Прыжки', 'Время по встречной', 'Пройденные режимы', 'Выполненный квест'],
      cpReq: ['Battle Zone', 'Delivery', 'Chase', 'Combo', 'Driving Time', 'Drift', 'Skill Pass', 'Jump', 'Reckless', 'GameMode', 'Quest'], cpNeed: '[ Условие ]', cpNow: '[ Сейчас ]', cpNot: 'Ещё не выполнено', cpReady: '★ Купон готов: обменяйте у дилера.', cpTaken: '✓ Купон уже получен.',
      cpCoupon: '★ Купон', cpHelp: '1. Получите купон, выполнив условие. 2. Обменяйте у дилера в Battledome.', cpGive: 'Выдать купон (GM)', cpGiven: '✓ Купон {n} в инвентаре.', cpMin: 'мин',
      lMoney: 'Деньги владения лицензиями:', lCount: '{n} из {m} лицензий', lHas: '✓ Есть эта лицензия', lHasnt: 'Нет этой лицензии', lEffect: 'Эффект', lCond: 'Как получить', lGive: 'Выдать лицензию (GM)', lTake: 'Забрать лицензию (GM)', lHelp: 'Деньги владения обнуляются 1-го числа; сумма зависит от лицензий персонажа.',
      skLevel: 'Уровень производства', skGroups: { low: 'Низкий навык', med: 'Средний навык', high: 'Высокий навык', 'very high': 'Максимальный навык', level: 'Навык уровня' }, skHelp: 'Уровень растёт с опытом изготовления предметов по книгам.',
      skLearned: '✓ Изучено', skNot: 'Не изучено', skReq: 'Уровень производства {n}', skMats: 'Материалы', skMakes: 'Создаёт', skLearn: 'Обучить (GM)', skForget: 'Забыть (GM)',
      dsFull: 'Только машина (во всё окно)', dsScene: 'Сменить фон: магазин / гараж', dsHomeHint: 'Выберите Визуал, Тюнинг или Прочее, чтобы увидеть предметы для этой машины.', dsSelList: 'Выбор', dsBuyAll: 'Купить надетые предметы', dsDefault: 'Сброс', dsCategory: 'Категория', dsPurchase: 'Купить', dsCheckout: 'Оформить покупку', dsPeriod: 'Срок', dsDays: '{n} дн.', dsForever: 'Навсегда', dsTotal: 'Итого:', dsSubs: { AERO: 'Аэро', AERO_ADV: 'Аэро', BOOSTER: 'Бустер', TIREWHEEL: 'Шины / колёса', AEROWING: 'Аэрокрыло', BOOSTERWING: 'Бустер-крыло', 'Air Duct': 'Воздухозаборник', TIRE: 'Шины', GLOSSTIRE: 'Глянцевые шины', SPOILER: 'Спойлер', CARREMODELING: 'Модификация', PAINT: 'Краска', PAINTHIGHGLOSS: 'Краска', UNDERNEON: 'Неон', WINDOWTINTING: 'Тонировка', DECAL: 'Наклейка', NUMBERPLATE: 'Номер', SOUND: 'Звук', STICKERLICENSE: 'Стикер' }, ctlTitle: 'Машина', ctlLeft: 'Левый поворотник', ctlRight: 'Правый поворотник', ctlHazard: 'Аварийка', ctlBrake: 'Стоп-сигнал', ctlHead: 'Фары', ctlSteer: 'Повернуть колёса (до 65°; двойной щелчок — прямо)', ctlFold: 'Показать / скрыть управление', ctlAuto: 'Вращать само',
      shHome: 'HOME', shVisual: 'Визуал', shTuning: 'Тюнинг', shOther: 'Прочее', shAll: 'Все', shHomeT: 'Купленные предметы попадают во вкладку Drift Item инвентаря (мгновенные — нет).\nПредметы Drift Shop нельзя перепродать или выставить на аукцион.\nЗдесь лаунчер покупает для выбранного персонажа за его Mito или CC.',
      shMito: 'Доступно Mito', shCC: 'Доступно CC', shBuy: 'Купить', shCar: 'Машина', shPeriod: 'Срок', shBought: '✓ Куплено: {n}.', shExtended: '✓ Срок продлён: {n}.', shForGood: 'навсегда', shDays: '{n} дн.', shPick: 'Выберите предмет.', shBonus: 'Бонус', shOnCar: 'сразу ставится на выбранную машину', shSearch: 'Поиск',
      shStats: ['Скорость', 'Ускорение', 'Удар', 'Буст'], shGrade: 'Характеристики машины (V1-V9)',
      gSelCC: 'Выбрать CC', gSelMito: 'Выбрать Mito', gMyCC: 'Мои CC', gMyMito: 'Мои Mito', gCostCC: 'Цена CC Gotcha (x1)', gCostMito: 'Цена Mito Gotcha (x1)', gChances: 'Шанс:', gCongrats: 'Поздравляем, вы выиграли:', gBoxNote: 'Коробка с машиной в инвентаре. Откройте её, и машина займёт место в гараже.', gPointsNote: 'Capsule Points в инвентаре.',
      gTitle: 'DRIFTCITY GOTCHA', gCC: 'CC Gotcha', gMito: 'Mito Gotcha', gSpin: 'Крутить для {n}', gWon: 'Вы выиграли', gPoints: '10 Capsule Points', gSlot: 'Слот {n}', gHint: 'Каждая прокрутка даёт машину из слотов (подарочная коробка V1) или 10 Capsule Points. Откройте коробку в игре.',
      err3: { no_runner: 'Персонаж не найден.', already_friend: 'Уже в друзьях.', msg_blocked: 'Этот персонаж вас заблокировал.', no_item: 'Предмет не найден.', coupon_taken: 'Этот купон уже получен.', shop_price: 'Такой цены больше нет.', no_cc: 'Не хватает CC.', gotcha_off: 'На этом сервере нет Gotcha.' },
    },
  };
  for (const l of Object.keys(X)) {
    const tx = window.TX[l];
    const extra = X[l].err3; delete X[l].err3;
    Object.assign(tx, X[l]);
    tx.err = Object.assign({}, tx.err || {}, extra);
  }
})();

const N = (v) => Number(v || 0).toLocaleString();
const moreApi = (ctx, cmd, args) => window.odc.more(cmd, ctx.accId, ctx.cid, args || {});
const okMsg = (s) => `<span class="ok">${esc(s)}</span>`;
const badMsg = (e) => `<span class="bad">${esc(typeof e === 'string' ? e : errText(e))}</span>`;
async function moreLoad(ctx, cmd, args) {
  try { const d = await moreApi(ctx, cmd, args); ctx.mito = d.mito; ctx.cc = d.cc; ctx.cname = d.name; return d; } catch (e) { ctx.msg = badMsg(e); return null; }
}
const itemPic = (id, cls) => { const s = ICONS.get('item:' + String(id || '').toLowerCase()); return s ? `<img class="${cls || ''}" src="${s}" alt="">` : ''; };

// ---------------------------------------------------------------- Community
MORE_PAGES.community = async (ctx) => {
  ctx.view = ctx.view || 'friends';
  const d = await moreLoad(ctx, 'community');
  const friends = d ? d.friends : [], msgs = d ? d.msgs : [];
  const views = [['friends', T.cFriends], ['add', T.cAdd, 'act'], ['del', T.cDel, 'act'], null, ['blocks', T.cBlocks], ['block', T.cBlock, 'act'], ['unblock', T.cUnblock, 'act'], null,
    ['inbox', T.cInbox], ['saved', T.cSaved], ['new', T.cNew]];
  let table = '';
  const v = ctx.view;
  if (v === 'friends' || v === 'blocks') {
    const list = friends.filter((f) => (v === 'blocks' ? f.state === 'B' : f.state !== 'B'));
    table = `<table class="mt"><thead><tr><th style="width:70px">${esc(T.cLevel)}</th><th>${esc(T.cNameCol)}</th><th>${esc(T.cCrew)}</th><th>${esc(T.cWhere)}</th></tr></thead><tbody>
      ${list.map((f) => `<tr class="${ctx.pick === f.name ? 'on' : ''}" data-fn="${esc(f.name)}"><td><b>${f.level}</b></td><td><b>${esc(f.name)}</b></td><td>${esc(f.team || '—')}</td>
        <td>${f.state === 'R' ? `<span class="muted">${esc(T.cAsked)}</span>` : f.state === 'C' ? `<span class="warn">${esc(T.cAsking)}</span> <button class="btn sm" data-acc="${f.cid}">${esc(T.cAccept)}</button>`
          : f.state === 'B' ? '—' : f.online ? `<span class="ok">${esc(T.cOnline)}</span>` : `<span class="muted">${esc(T.cOffline)}</span>`}</td></tr>`).join('')
      || `<tr><td colspan="4" class="muted">${esc(T.cNone)}</td></tr>`}</tbody></table>`;
  } else if (v === 'inbox' || v === 'saved') {
    const list = msgs.filter((m) => (v === 'saved' ? m.state === 'K' : m.state !== 'K'));
    const open = list.find((m) => m.mid === ctx.mid);
    table = `<table class="mt"><thead><tr><th style="width:140px">${esc(T.cFrom)}</th><th>${esc(T.cText)}</th><th style="width:140px">${esc(T.cDate)}</th></tr></thead><tbody>
      ${list.map((m) => `<tr class="${m.mid === ctx.mid ? 'on' : ''}" data-mid="${m.mid}"><td><b>${esc(m.from)}</b>${m.state === 'N' ? ` <span class="pill">${esc(T.cNewMsg)}</span>` : ''}</td><td class="ell">${esc(m.text)}</td><td>${esc(m.date)}</td></tr>`).join('')
      || `<tr><td colspan="3" class="muted">${esc(T.cNone)}</td></tr>`}</tbody></table>
      ${open ? `<div class="mread"><div><b>${esc(open.from)}</b> <span class="muted small">${esc(open.date)}</span></div><p>${esc(open.text)}</p>
        <div class="row">${v === 'inbox' ? `<button class="btn sm" id="cKeep">${esc(T.cKeep)}</button>` : ''}<button class="btn sm" id="cDelM">${esc(T.cDelMsg)}</button>
        <button class="btn sm" id="cReply">${esc(T.cNew)}</button></div></div>` : ''}`;
  } else if (v === 'new') {
    table = `<div class="mnew"><label>${esc(T.cTo)}<input id="cTo" maxlength="20" value="${esc(ctx.to || '')}"></label>
      <label>${esc(T.cText)}<textarea id="cTxt" maxlength="200" rows="6"></textarea></label><div class="row"><button class="btn primary" id="cSend">${esc(T.cSend)}</button></div></div>`;
  }
  ctx.frame(`<div class="mcom"><div class="mside">${views.map((x) => (x ? `<button class="mside-b${x[0] === v ? ' on' : ''}${x[2] ? ' act' : ''}" data-v="${x[0]}">${esc(x[1])}</button>` : '<span class="gap"></span>')).join('')}
      <span class="grow"></span><input id="cWho" placeholder="${esc(T.cName)}" maxlength="20" value="${esc(ctx.pick || '')}"></div>
    <div class="mmain">${table}<div class="mfoot">${ctx.msg || ''}</div></div></div>`, T.mSubCom);
  ctx.msg = '';
  const act = async (cmd, name) => {
    if (!name) { ctx.msg = badMsg(T.cNeedName); return ctx.redraw(); }
    try { const r = await moreApi(ctx, cmd, { name }); ctx.msg = okMsg(t('cDone', { n: r.name || name })); } catch (e) { ctx.msg = badMsg(e); }
    ctx.redraw();
  };
  $$('.mside-b').forEach((b) => b.onclick = () => {
    const who = $('#cWho').value.trim();
    const k = b.dataset.v;
    if (k === 'add') return act('friend_add', who);
    if (k === 'del') return act('friend_del', who);
    if (k === 'block') return act('block', who);
    if (k === 'unblock') return act('unblock', who);
    ctx.view = k; ctx.mid = null; if (k === 'new') ctx.to = who; ctx.redraw();
  });
  $$('[data-fn]').forEach((r) => r.onclick = (e) => { if (e.target.closest('button')) return; ctx.pick = r.dataset.fn; $('#cWho').value = ctx.pick; $$('[data-fn]').forEach((x) => x.classList.toggle('on', x === r)); });
  $$('[data-acc]').forEach((b) => b.onclick = async () => { try { await moreApi(ctx, 'friend_accept', { fcid: Number(b.dataset.acc) }); } catch (e) { ctx.msg = badMsg(e); } ctx.redraw(); });
  $$('[data-mid]').forEach((r) => r.onclick = async () => {
    ctx.mid = Number(r.dataset.mid);
    const m = msgs.find((x) => x.mid === ctx.mid);
    if (m && m.state === 'N') { try { await moreApi(ctx, 'msg_read', { mid: m.mid }); } catch { /* game open: stays new */ } }
    ctx.redraw();
  });
  const msgAct = async (cmd) => { try { await moreApi(ctx, cmd, { mid: ctx.mid }); ctx.mid = null; } catch (e) { ctx.msg = badMsg(e); } ctx.redraw(); };
  if ($('#cKeep')) $('#cKeep').onclick = () => msgAct('msg_keep');
  if ($('#cDelM')) $('#cDelM').onclick = () => msgAct('msg_del');
  if ($('#cReply')) $('#cReply').onclick = () => { const m = msgs.find((x) => x.mid === ctx.mid); ctx.view = 'new'; ctx.to = m ? m.from : ''; ctx.redraw(); };
  if ($('#cSend')) $('#cSend').onclick = async () => {
    const name = $('#cTo').value.trim(), text = $('#cTxt').value.trim();
    if (!name) { ctx.msg = badMsg(T.cNeedName); return ctx.redraw(); }
    try { await moreApi(ctx, 'msg_send', { name, text }); ctx.msg = okMsg(t('cSent', { n: name })); ctx.view = 'inbox'; } catch (e) { ctx.msg = badMsg(e); }
    ctx.redraw();
  };
};

// ---------------------------------------------------------------- Ranking
MORE_PAGES.ranking = async (ctx) => {
  ctx.tab = ctx.tab || 'game';
  const d = await moreLoad(ctx, 'ranking');
  const carTxt = d && d.car ? `(V${d.grade || 1}) ${d.car}` : '—';
  let body;
  if (ctx.tab === 'game') {
    body = `<div class="rkgrid">${(d ? d.cats : []).map((c) => `<div class="rk">
      <div class="rkh"><b>${esc(T.rCats[c.key] || c.key)}</b><span class="grow"></span><button class="rkd" data-top="${c.key}">${esc(T.rDetail)}</button></div>
      <div class="rkl"><span>${esc(T.rPos)}</span><span>${esc(T.rRec)} (${esc(T.rUnits[c.key] || '')})</span><span>${esc(T.rLast)}</span><span>${esc(T.rCar)}</span></div>
      <div class="rkv"><span>${c.pos ? `#${c.pos}` : esc(T.rNone)}</span><span class="rec">${N(c.value)}</span><span class="last">- 0</span><span>${esc(carTxt)}</span></div>
      ${ctx.top === c.key ? `<div class="rktop"><b>${esc(T.rTop)}</b>${c.top.length ? c.top.map((x, i) => `<div><span>${i + 1}.</span><span>${esc(x.name)} <i class="muted">Lv ${x.level}</i></span><span>${N(x.value)}</span></div>`).join('') : `<div class="muted">${esc(T.cNone)}</div>`}</div>` : ''}
    </div>`).join('')}</div>`;
  } else {
    const teams = d ? d.teams : [];
    body = teams.length ? `<div class="mmain"><table class="mt"><thead><tr><th style="width:50px">#</th><th>${esc(T.rTeam)}</th><th>${esc(T.rMaster)}</th><th>${esc(T.rMembers)}</th><th>${esc(T.rPoints)}</th><th>${esc(T.rWins)}</th><th>${esc(T.rCreated)}</th></tr></thead>
      <tbody>${teams.map((x, i) => `<tr><td><b>${i + 1}</b></td><td><b>${esc(x.name)}</b></td><td>${esc(x.master)}</td><td>${x.members}</td><td>${N(x.points)}</td><td>${N(x.wins)}</td><td>${esc(x.created)}</td></tr>`).join('')}</tbody></table></div>`
      : `<div class="soonbox"><span>${esc(T.rNoCrew)}</span></div>`;
  }
  ctx.frame(`<div class="mtabs"><button class="mtab${ctx.tab === 'game' ? ' on' : ''}" data-tab="game">${esc(T.rGame)}</button><button class="mtab${ctx.tab === 'crews' ? ' on' : ''}" data-tab="crews">${esc(T.rCrews)}</button>
    <span class="grow"></span><span class="muted small">${esc(T.rReset)}</span></div>${ctx.msg ? `<div class="mfoot">${ctx.msg}</div>` : ''}${body}`, T.mSubRank);
  ctx.msg = '';
  $$('[data-tab]').forEach((b) => b.onclick = () => { ctx.tab = b.dataset.tab; ctx.redraw(); });
  $$('[data-top]').forEach((b) => b.onclick = () => { ctx.top = ctx.top === b.dataset.top ? null : b.dataset.top; ctx.redraw(); });
};

// ---------------------------------------------------------------- Coupon Book
MORE_PAGES.coupon = async (ctx) => {
  const d = await moreLoad(ctx, 'coupon');
  const list = d ? d.coupons : [];
  const key = (c) => `${c.dbType}:${c.dbIdx}`;
  const need = (c) => (c.count > 0 ? c.count : c.minutes > 0 ? c.minutes : 0);
  const unit = (c) => (c.minutes > 0 ? T.cpMinutes : T.cpTimes);
  const done = (c) => need(c) > 0 && c.now >= need(c);
  const logo = (c, cls) => { const s = ICONS.get('logo:' + c.model); return s ? `<img class="${cls}" src="${s}" alt="${esc(c.car)}">` : `<b>${esc(c.car)}</b>`; };
  if (!ctx.sel && list[0]) ctx.sel = key(list.find((c) => c.grade === 2) || list[0]);
  const grades = [2, 3, 4, 5, 6, 7, 8, 9];
  const cell = (c) => `<button class="cp${key(c) === ctx.sel ? ' on' : ''}${c.state === 3 ? ' taken' : done(c) ? ' ready' : ''}" data-cp="${key(c)}">
      <span class="cplogo">${logo(c, 'cpl')}</span><span>${esc(T.cpReq[c.type] || '')}</span><span>${need(c) ? N(need(c)) : ''}</span>
      <i>${c.state === 3 ? '✓ ' + esc(T.cpCoupon) : done(c) ? esc(T.cpCoupon) : `${N(c.now)} ${esc(unit(c))}`}</i></button>`;
  const grid = grades.map((g) => `<div class="cprow"><div class="cpv">V${g}</div><div class="cpcells">${list.filter((c) => c.grade === g).map(cell).join('')}</div></div>`).join('');
  ctx.frame(`<div class="mcp"><div class="cpgrid">${grid}</div><div class="cpside" id="cpSide">
      <div class="cphd"><div class="cpbadge" id="cpBadge"></div><div class="cpreq"><div class="muted small">${esc(T.cpNeed)}</div><div class="cpbox" id="cpNeed"></div>
        <div class="muted small">${esc(T.cpNow)}</div><div class="cpbox r" id="cpNowB"></div></div></div>
      <div class="cpname" id="cpName"></div>
      <div class="cp3d" id="cp3d"><span class="cp3hint">⟲ 360°</span></div>
      <div class="cpstats" id="cpStats"></div>
      <div class="cpprice"><span>${esc(T.cpPrice)}</span><b id="cpPrice"></b><i>M</i></div>
      <div class="cpstate small" id="cpState"></div>
      <div class="muted small">${esc(T.cpHelp)}</div>
      <div class="mfoot" id="cpMsg">${ctx.msg || ''}</div>
      ${ctx.gm ? `<button class="btn gmb" id="cpGive">${esc(T.cpGive)}</button>` : ''}</div></div>`, T.mSubCp);
  ctx.msg = '';
  const pv = window.Garage && window.Garage.preview($('#cp3d'), null, { yaw: -0.7 });
  ctx.cleanup = () => pv && pv.dispose();
  const fill = () => {
    const c = list.find((x) => key(x) === ctx.sel);
    if (!c) return;
    $$('[data-cp]').forEach((b) => b.classList.toggle('on', b.dataset.cp === ctx.sel));
    $('#cpBadge').innerHTML = `<span>COUPON</span><b>${esc(c.car)}</b>`;
    $('#cpNeed').innerHTML = `<span class="warn">:::${esc(T.cpReqT)}:::</span><br>${esc(t('cpReqLine', { r: T.cpReqLong[c.type] || T.cpReq[c.type] || '', n: N(need(c)), u: unit(c) }))}`;
    $('#cpNowB').textContent = `${N(c.now)} ${unit(c)}`;
    $('#cpName').innerHTML = `${logo(c, 'cpnl')}<span class="cpvg">V${c.grade}</span>`;
    const lab = [T.cpSpeed, T.cpAccel, T.cpDura, T.cpBoost];
    $('#cpStats').innerHTML = `<div class="cpst"><span class="warn">${esc(T.cpLevel)}</span><b class="cplv">${esc(t('cpLvl', { n: c.lvl || 1 }))}</b></div>`
      + c.stats.map((v, k) => `<div class="cpst"><span class="warn">${esc(lab[k])} <i>[ ${v} ]</i></span><div class="bar"><i style="width:${Math.min(100, v / 3)}%"></i></div></div>`).join('');
    $('#cpPrice').textContent = N(c.price);
    $('#cpState').innerHTML = `<b class="${c.state === 3 || done(c) ? 'ok' : 'muted'}">${esc(c.state === 3 ? T.cpTaken : done(c) ? T.cpReady : T.cpNot)}</b>`;
    if ($('#cpGive')) $('#cpGive').disabled = c.state === 3;
    if (pv) pv.set({ model: c.model, name: c.name, tire: c.tire, tire_scale: c.tire_scale, tire_width: c.tire_width });
  };
  $$('[data-cp]').forEach((b) => b.onclick = () => { ctx.sel = b.dataset.cp; $('#cpMsg').innerHTML = ''; fill(); });
  if ($('#cpGive')) $('#cpGive').onclick = async () => {
    const c = list.find((x) => key(x) === ctx.sel);
    try { await moreApi(ctx, 'coupon_give', { dbType: c.dbType, dbIdx: c.dbIdx }); ctx.msg = okMsg(t('cpGiven', { n: c.car })); } catch (e) { ctx.msg = badMsg(e); }
    ctx.redraw();
  };
  fill();
  loadIcons(list.map((c) => 'logo:' + c.model)).then((ch) => {
    if (!ch || !$('#cpSide')) return;
    $$('[data-cp]').forEach((b) => { const c = list.find((x) => key(x) === b.dataset.cp); if (c) b.querySelector('.cplogo').innerHTML = logo(c, 'cpl'); });
    const c = list.find((x) => key(x) === ctx.sel); if (c) $('#cpName').innerHTML = `${logo(c, 'cpnl')}<span class="cpvg">V${c.grade}</span>`;
  });
};

// ---------------------------------------------------------------- Licenses
MORE_PAGES.license = async (ctx) => {
  const d = await moreLoad(ctx, 'license');
  // License.xlt is English: Portuguese and Russian from lic_i18n.js
  const tr = (x) => (window.licText ? window.licText(x, L) : x);
  const lics = (d ? d.licenses : []).map((l) => Object.assign({}, l, { name: tr(l.name), info: tr(l.info), effect: tr(l.effect), cond: tr(l.cond) }));
  const grades = [...new Set(lics.map((l) => l.grade))].sort((a, b) => a - b);
  if (!ctx.sel && lics[0]) ctx.sel = lics[0].id;
  const sel = lics.find((l) => l.id === ctx.sel);
  const cond = (s) => String(s || '').replace(/%d%%/g, 'X%').replace(/%d/g, 'X').replace(/%%/g, '%');
  ctx.frame(`<div class="lictop"><span class="muted">${esc(T.lMoney)}</span><b class="licm">${N(d && d.money)}</b><span class="muted">Mito</span><span class="grow"></span>
      <span class="muted small">${esc(t('lCount', { n: lics.filter((l) => l.held).length, m: lics.length }))}</span></div>
    <div class="mlic"><div class="licrows">${grades.map((g) => `<div class="licrow"><div class="licg">${N(g)}</div><div class="licts">${lics.filter((l) => l.grade === g).map((l) => `
      <button class="lic${l.held ? ' held' : ''}${l.id === ctx.sel ? ' on' : ''}${itemPic(l.icon) ? ' pic' : ''}" data-lic="${l.id}"${Tip.attr({ name: l.name, desc: l.info, lines: [l.effect, l.held ? T.lHas : T.lHasnt] })}>${itemPic(l.icon) || esc(l.name)}</button>`).join('')}</div></div>`).join('')}</div>
    <div class="licside">${sel ? `<div class="lichd">${itemPic(sel.icon, 'licbig')}<h3>${esc(sel.name)}</h3></div><div class="small ${sel.held ? 'ok' : 'muted'}"><b>${esc(sel.held ? T.lHas : T.lHasnt)}</b></div>
      <div class="licscroll" tabindex="0"><p>${esc(sel.info)}</p>
      <div class="muted small">${esc(T.lEffect)}</div><div class="ok small pre">${esc(sel.effect)}</div>
      <div class="muted small">${esc(T.lCond)}</div><div class="small pre">${esc(cond(sel.cond))}</div></div>` : '<span class="grow"></span>'}
      <div class="mfoot">${ctx.msg || ''}</div>
      ${ctx.gm && sel ? `<button class="btn gmb" id="licSet">${esc(sel.held ? T.lTake : T.lGive)}</button>` : ''}<div class="muted small">${esc(T.lHelp)}</div></div></div>`, T.mSubLic);
  ctx.msg = '';
  $$('[data-lic]').forEach((b) => b.onclick = () => { ctx.sel = Number(b.dataset.lic); ctx.redraw(); });
  if (!ctx.licIcons) { ctx.licIcons = true; loadIcons(lics.map((l) => 'item:' + l.icon.toLowerCase())).then((ch) => { if (ch && document.querySelector('.mlic')) ctx.redraw(); }); }
  if ($('#licSet')) $('#licSet').onclick = async () => {
    try { await moreApi(ctx, 'license_set', { lid: sel.id, on: !sel.held }); ctx.msg = okMsg(t('cDone', { n: sel.name })); } catch (e) { ctx.msg = badMsg(e); }
    ctx.redraw();
  };
};

// ---------------------------------------------------------------- Production Skill Book
MORE_PAGES.skill = async (ctx) => {
  const d = await moreLoad(ctx, 'skill');
  const books = d ? d.books : [];
  const groups = ['low', 'med', 'high', 'very high', 'level'];
  const sel = books.find((b) => b.id === ctx.sel);
  const draw = () => {
    const cells = (g) => {
      const bs = books.filter((b) => b.group === g);
      const pad = Math.max(0, Math.ceil(Math.max(bs.length, 1) / 12) * 12 - bs.length);
      return bs.map((b) => `<button class="skc${b.learned ? ' on' : ''}${b.id === ctx.sel ? ' sel' : ''}" data-sk="${esc(b.id)}"${Tip.attr({ name: b.name, desc: `${T.skMakes}: ${b.resultName}${b.count > 1 ? ' ×' + b.count : ''}`, lines: [t('skReq', { n: b.req }), `${T.skMats}: ${b.mats.map((m) => `${m[0]} ×${m[1]}`).join(', ')}`, b.learned ? T.skLearned : T.skNot] })}>${itemPic(b.result) || `<span>${esc(b.resultName.slice(0, 10))}</span>`}</button>`).join('')
        + '<span class="skc empty"></span>'.repeat(pad);
    };
    ctx.frame(`<div class="sktop"><span class="grow"></span><div class="sklv"><span class="warn">${esc(T.skLevel)}</span><b>${esc(d ? d.skName : '')}</b><div class="bar"><i style="width:${d ? d.skPct : 0}%"></i></div><b class="warn">${d ? d.skPct : 0} %</b></div></div>
      <div class="skbody">${groups.map((g) => `<div class="skrow"><div class="skg">${esc(T.skGroups[g])}</div><div class="skcells">${cells(g)}</div></div>`).join('')}</div>
      <div class="skfoot"><span class="muted small">${esc(sel ? `${sel.name} — ${sel.learned ? T.skLearned : T.skNot}` : T.skHelp)}</span><span class="grow"></span><span>${ctx.msg || ''}</span>
        ${ctx.gm && sel ? `<button class="btn gmb sm" id="skSet">${esc(sel.learned ? T.skForget : T.skLearn)}</button>` : ''}</div>`, T.mSubSk);
    $$('[data-sk]').forEach((b) => b.onclick = () => { ctx.sel = b.dataset.sk; ctx.msg = ''; ctx.redraw(); });
    if ($('#skSet')) $('#skSet').onclick = async () => {
      try { await moreApi(ctx, 'skill_set', { book: sel.id, on: !sel.learned }); ctx.msg = okMsg(t('cDone', { n: sel.name })); } catch (e) { ctx.msg = badMsg(e); }
      ctx.redraw();
    };
  };
  draw(); ctx.msg = '';
  loadIcons(books.map((b) => 'item:' + b.result.toLowerCase())).then((ch) => { if (ch && document.querySelector('.skbody')) draw(); });
};

// ---------------------------------------------------------------- Drift Shop
// the drift shop's try-on: one slot per kind of look (paints share one, tires and glossy tires share the wheels)
const SLOT = (cat) => (cat === 1 || cat === 32 ? 'paint' : cat === 8 || cat === 48 ? 'tire' : String(cat));
const NEON_RGB = { blue: [0.2, 0.45, 1], red: [1, 0.15, 0.15], green: [0.2, 1, 0.3], yellow: [1, 0.9, 0.2], pink: [1, 0.35, 0.75], purple: [0.65, 0.3, 1],
  white: [1, 1, 1], orange: [1, 0.55, 0.1], violet: [0.6, 0.3, 1], sky: [0.4, 0.8, 1] };
const colorWord = (name) => { const n = String(name || '').toLowerCase(); const k = Object.keys(NEON_RGB).find((w) => n.includes(w)); return k ? NEON_RGB[k] : null; };
const SHOP_OPT_KEY = 'odcShopOpts';
const shopOpts = () => { let o; try { o = Object.assign({ music: 50 }, JSON.parse(localStorage.getItem(SHOP_OPT_KEY) || '{}')); } catch { o = { music: 50 }; } o.gfx = window.Garage ? window.Garage.gfxGet() : 'mid'; return o; };
const saveShopOpts = (o) => { try { localStorage.setItem(SHOP_OPT_KEY, JSON.stringify(o)); } catch { /* private */ } };

MORE_PAGES.shop = async (ctx) => {
  ctx.tab = ctx.tab || 'tuning';
  if (!ctx.shop || ctx.shopCid !== ctx.cid || ctx.reload) {
    ctx.shop = await moreLoad(ctx, 'shop'); ctx.shopCid = ctx.cid; ctx.reload = false;
    ctx.cart = new Map();
  }
  const d = ctx.shop || { items: [], cars: [], wings: [], tires: [] };
  if (!ctx.cart) ctx.cart = new Map();
  const byUid = new Map(d.items.map((i) => [i.uid, i]));
  if (ctx.carIx == null || !d.cars[ctx.carIx]) ctx.carIx = Math.max(0, d.cars.findIndex((c) => c.current));
  const car = d.cars[ctx.carIx];
  const fits = new Set(car ? car.fits : []);
  const TOPS = { visual: ['TOP_COLOR', 'TOP_DECORATION'], tuning: ['TOP_TUNNING'], other: ['TOP_ETC'] };
  const O = shopOpts();
  const priceTxt = (p) => `${p.days ? t('shDays', { n: p.days }) : T.shForGood} · ${p.cc ? N(p.cc) + ' CC' : N(p.mito) + ' Mito'}`;
  const first = (i) => i.prices[0];
  // the items with the colour window: paint, neon, glass and the decals (their colour, as the paint tab)
  const COLOUR_CATS = [1, 32, 2, 3, 11];
  const optionsOf = (it) => {
    if (!it || !it.pick || !car) return [];
    // the Aero sets: A Type is always there (the car's own look; its basic kit when it has one), B / C the car's kits
    if (it.pick === 'aero') {
      const kits = car.aero.slice();
      const basic = kits.length && /basic|_01$/i.test(kits[0].name + ' ' + kits[0].file) ? kits.shift() : null;
      return [{ key: basic ? basic.vid : '0', label: 'A Type', name: basic ? basic.name : car.name, icon: '', file: basic ? basic.file : '', style: 1, plain: !basic },
        ...kits.map((a, k) => ({ key: a.vid, label: `${String.fromCharCode(66 + k)} Type`, name: a.name, icon: '', file: a.file, style: k + 2 }))];
    }
    // wings: the classic ones (i_d_s_...) and the car's own (<model>_sp01), as the game's bar
    if (it.pick === 'aerowing' || it.pick === 'boosterwing') return d.wings.filter((w) => w.type === (it.pick === 'aerowing' ? 1 : 2)
      && (car.wings ? car.wings.includes(w.id) : (/^i_d_s_/.test(w.file) || w.file.startsWith(car.model + '_'))))
      .sort((a, b) => (b.file.startsWith(car.model + '_') - a.file.startsWith(car.model + '_')) || b.id - a.id).map((w) => ({ key: String(w.id), label: w.name, name: w.name, icon: w.file, file: w.file }));
    if (it.pick === 'tirewheel') return d.tires.map((x) => ({ key: String(x.id), label: x.name, name: x.name, icon: x.icon, file: x.file }));
    return [];
  };
  const textOf = (it, opt, x) => {
    // the colour window's colour, as the game's: a Windows colour 0x00BBGGRR in decimal
    if (COLOUR_CATS.includes(it.cat) && x && x.rgb != null) return String(((x.rgb & 0xff) << 16) | (x.rgb & 0xff00) | ((x.rgb >> 16) & 0xff));
    if (it.cat === 9) return plateText(x && x.text);
    if (!it.pick || !opt) return '';
    if (it.pick === 'aero') return ' '.repeat(10) + String(car.type).padStart(3, '0') + String(opt.style) + String(opt.key).padStart(5, '0');
    return opt.key;
  };
  // a number plate's text: the game keeps 8 characters (16 bytes of UTF-16 in the car's visual item)
  const plateText = (v) => String(v == null ? '' : v).replace(/[^\x20-\x7e]/g, '').slice(0, 8);
  // the look of the car: what is on it (resolved by the helper), with the try-on over it (by slot)
  const lookList = () => {
    const out = new Map();
    for (const e of car ? car.look : []) out.set(SLOT(e.cat), e);
    for (const [slot, c] of ctx.cart) {
      const it = byUid.get(c.uid);
      if (!it) continue;
      if (c.opt && c.opt.plain) { out.delete(slot); continue; }     // A Type of a car without kits: its own look
      out.set(slot, { cat: it.cat, file: (c.opt && c.opt.file) || it.id.toLowerCase(), name: it.name, rgb: c.rgb != null ? c.rgb : it.rgb, pal: it.pal, rgbPicked: c.rgb != null,
        index: it.index, plate: it.cat === 9 ? (Number((/(\d+)$/.exec(it.id) || [])[1]) || 1) : undefined, text: it.cat === 9 ? plateText(c.text) : undefined });
    }
    return [...out.values()];
  };
  const carSpec = (keepView) => {
    const L = lookList();
    const G = window.Garage;
    const paint = L.find((e) => e.cat === 1 || e.cat === 32), tint = L.find((e) => e.cat === 3);
    return { model: car.model, type: car.type, name: car.name, tire: car.tire, tire_scale: car.tire_scale, tire_width: car.tire_width, color: car.color,
      paintPal: paint && paint.pal && !(paint.rgbPicked) ? paint.pal : null,
      paint: paint && paint.rgb != null && !(paint.pal && !paint.rgbPicked) ? paint.rgb : null, tint: tint && tint.rgb != null ? tint.rgb : null,
      parts: G.lookParts(car.model, L), look: (f) => G.lookBuild(car.model, L, f), keepView };
  };
  // the game's tabs: one Paint for all the paints, one Tire Wheel for tires / glossy tires / wheels, the wings together
  const GROUP = { PAINTHIGHGLOSS: 'PAINT', TIRE: 'TIREWHEEL', GLOSSTIRE: 'TIREWHEEL', SPOILER: 'AEROWING', AERO_ADV: 'AERO' };
  const ORDER = ['PAINT', 'WINDOWTINTING', 'UNDERNEON', 'DECAL', 'NUMBERPLATE', 'STICKERLICENSE', 'CARREMODELING', 'AERO', 'BOOSTER', 'TIREWHEEL', 'AEROWING', 'BOOSTERWING', 'Air Duct'];
  const subOf = (i) => GROUP[i.sub] || i.sub;
  const subsOf = (tab) => [...new Set(d.items.filter((i) => (TOPS[tab] || []).includes(i.top) && fits.has(i.uid)).map(subOf))]
    .sort((a, b) => (ORDER.indexOf(a) + 1 || 99) - (ORDER.indexOf(b) + 1 || 99));
  const subs = ctx.tab === 'home' ? [] : subsOf(ctx.tab);
  if (ctx.sub && !subs.includes(ctx.sub)) ctx.sub = null;
  const q = (ctx.q || '').toLowerCase();
  const shown = ctx.tab === 'home' ? [] : d.items.filter((i) => (TOPS[ctx.tab] || []).includes(i.top) && fits.has(i.uid) && (!ctx.sub || subOf(i) === ctx.sub) && (!q || i.name.toLowerCase().includes(q)))
    .sort((x, y) => x.order - y.order || x.name.localeCompare(y.name));
  const PER = 7;
  const pages = Math.max(1, Math.ceil(shown.length / PER));
  ctx.page = Math.min(ctx.page || 0, pages - 1);
  const sel = byUid.get(ctx.sel);
  const tabs = [['home', T.shHome], ['visual', T.shVisual], ['tuning', T.shTuning], ['other', T.shOther]];
  const logo = car ? (ICONS.get('logo:' + car.model) ? `<img class="dslogo" src="${ICONS.get('logo:' + car.model)}" alt="${esc(car.name)}">` : `<b class="dsname">${esc(car.name)}</b>`) : '';
  const icon = (id) => itemPic(id, 'dsico') || '<span class="dsico ph"></span>';
  const total = () => { let m = 0, c = 0; for (const x of ctx.cart.values()) { const it = byUid.get(x.uid); const p = it && it.prices[x.p || 0]; if (p) { m += p.mito || 0; c += p.cc || 0; } } return { m, c }; };
  const draw = () => {
    const opts = optionsOf(sel);
    const cur = sel ? ctx.cart.get(SLOT(sel.cat)) : null;
    const tot = total();
    ctx.frame(`<div class="mtabs big dstabs">${tabs.map(([k, n]) => `<button class="mtab${ctx.tab === k ? ' on' : ''}" data-tab="${k}">${esc(n)}</button>`).join('')}
        <span class="grow"></span><button class="dstool" id="dsFull" title="${esc(T.dsFull)}" aria-label="${esc(T.dsFull)}">⛶</button>
        <button class="dstool" id="dsScene" title="${esc(T.dsScene)}" aria-label="${esc(T.dsScene)}">${ctx.bg === 'garage' ? '◻' : '🏠'}</button>
        <button class="dstool" id="dsOpt" title="${esc(T.garOptions || 'Options')}" aria-label="${esc(T.garOptions || 'Options')}">⚙</button></div>
      <div class="shsubs">${ctx.tab === 'home' ? `<span class="muted small">${esc(T.dsHomeHint)}</span>` : [`<button class="shsub${!ctx.sub ? ' on' : ''}" data-sub="">${esc(T.shAll)}</button>`, ...subs.map((x) => `<button class="shsub${ctx.sub === x ? ' on' : ''}" data-sub="${esc(x)}">${esc(T.dsSubs[x] || x.replace(/_/g, ' ').toLowerCase())}</button>`)].join('')}
        ${ctx.tab === 'home' ? '' : `<span class="grow"></span><input id="shQ" placeholder="${esc(T.shSearch)}" value="${esc(ctx.q || '')}">`}</div>
      <div class="dsbody">
        <div class="dsstage" id="dsStage">
          <div class="dshead">${d.cars.length > 1 ? '<button class="dsarr" id="dsPrevCar" aria-label="prev">◀</button>' : ''}<span class="dscar">${logo}<span class="dsv">V${car ? car.grade : ''}</span></span>${d.cars.length > 1 ? '<button class="dsarr" id="dsNextCar" aria-label="next">▶</button>' : ''}</div>
          <div class="dssel"><b>${esc(T.dsSelList)}</b>${[...ctx.cart.entries()].map(([slot, x]) => { const it = byUid.get(x.uid); return it ? `<div class="dsselit" title="${esc(it.name + (x.opt ? ' — ' + x.opt.label : ''))}">${icon(it.id)}<button class="dsrm" data-rm="${esc(slot)}" aria-label="✕">✕</button></div>` : ''; }).join('')}</div>
          ${sel && COLOUR_CATS.includes(sel.cat) && cur ? (() => {
            const rgb = cur.rgb != null ? cur.rgb : (sel.rgb != null ? sel.rgb : 0x808080);
            const hex = '#' + rgb.toString(16).padStart(6, '0');
            return `<div class="dscol"><div class="dssv" id="dsSV" style="background-color:hsl(${ctx.hue || 0},100%,50%)"><i></i></div>
              <input type="range" class="dshue" id="dsHue" min="0" max="359" value="${ctx.hue || 0}" aria-label="Hue">
              <div class="dscur"><span style="background:${hex}"></span><code>${hex.toUpperCase()}</code></div></div>`;
          })() : ''}
          ${sel && sel.cat === 9 && cur ? `<div class="dscol dsplate"><label>${esc(T.dsSubs.NUMBERPLATE)}<input id="dsPlate" maxlength="8" spellcheck="false" placeholder="DRIFT CITY" value="${esc(cur.text || '')}"></label></div>` : ''}
          ${opts.length ? `<div class="dsopts"><div class="dsoptsin">${opts.map((o) => `<button class="dsopt${cur && cur.opt && cur.opt.key === o.key ? ' on' : ''}" data-opt="${esc(o.key)}" title="${esc(o.name)}">${o.icon ? icon(o.icon) : `<span class="dsico ph big">${esc(o.label[0])}</span>`}<span>${esc(o.label)}</span></button>`).join('')}</div></div>` : ''}
          <div class="dsctl">${window.Garage ? window.Garage.ctlBar(T, { auto: true, still: ctx.st && ctx.st.ctl.still, hidden: ctx.ctlFolded }) : ''}</div>
          <div class="dsbuy"><button class="dsbuyall" id="dsBuyAll" ${ctx.cart.size ? '' : 'disabled'}>↵ ${esc(T.dsBuyAll)}${ctx.cart.size ? ` <small>(${tot.m ? N(tot.m) + ' Mito' : ''}${tot.m && tot.c ? ' + ' : ''}${tot.c ? N(tot.c) + ' CC' : ''})</small>` : ''}</button></div>
          <button class="dsdef" id="dsDef">⟲ ${esc(T.dsDefault)}</button>
          <button class="dsexit" id="dsExit" title="${esc(T.dsFull)}">✕</button>
          <div class="dsoptpanel" id="dsOptPanel" hidden><h3>${esc(T.garOptions || 'Options')}</h3>
            <div class="gp-row"><span>${esc(T.garGfx || 'Graphics')}</span><div class="gseg">${['low', 'mid', 'high'].map((g) => `<button data-gfx="${g}" class="${O.gfx === g ? 'on' : ''}">${esc(T['garGfx_' + g] || g)}</button>`).join('')}</div></div>
            <label class="gp-row"><span>${esc(T.garMusic || 'Music')}</span><input type="range" id="dsVol" min="0" max="100" step="5" value="${O.music}"><output>${O.music}%</output></label><p class="warn3d small">⚠ ${esc(T.v3dWarn || '')}</p></div>
        </div>
        <div class="dsright">${ctx.tab === 'home' ? `<div class="shhome">${esc(T.shHomeT).replace(/\n/g, '<br>')}</div>` : `
          <div class="dscat"><button class="dsarr sm" id="dsPgL" ${ctx.page ? '' : 'disabled'}>◀</button><span>${esc(T.dsCategory)}: ${esc(ctx.sub ? (T.dsSubs[ctx.sub] || ctx.sub) : T.shAll)}</span><button class="dsarr sm" id="dsPgR" ${ctx.page < pages - 1 ? '' : 'disabled'}>▶</button></div>
          <div class="dslist">${shown.slice(ctx.page * PER, ctx.page * PER + PER).map((i) => `<div class="dsit${ctx.cart.has(SLOT(i.cat)) && ctx.cart.get(SLOT(i.cat)).uid === i.uid ? ' on' : ''}${i.uid === ctx.sel ? ' sel' : ''}" data-it="${esc(i.uid)}"${Tip.attr({ name: i.name, desc: i.desc, lines: [...i.prices.map(priceTxt), i.bonus.some(Boolean) ? `${T.shBonus}: ${i.bonus.map((b, k) => (b ? `${T.shStats[k]} +${b}` : '')).filter(Boolean).join(' · ')}` : ''] })}>
              <div class="dsiw">${icon(i.id)}</div><div class="dsii"><b>${esc(i.name)}</b><span class="${first(i).cc ? 'cc' : 'mi'}">${first(i).cc ? '◉ ' + N(first(i).cc) : 'Ⓜ ' + N(first(i).mito)}</span>
              <button class="dsp" data-buy="${esc(i.uid)}">${esc(T.dsPurchase)}</button></div></div>`).join('') || `<div class="muted small">${esc(T.cNone)}</div>`}</div>
          <div class="dspage">${ctx.page + 1} / ${pages}</div>`}
        </div></div>
      <div class="shfoot"><span class="shm">${esc(T.shMito)}<b>${N(ctx.mito)}</b></span><span class="shc">${esc(T.shCC)}<b>${N(ctx.cc)}</b></span><span class="grow"></span><span id="dsMsg">${ctx.msg || ''}</span></div>`, T.mSubShop);
    ctx.msg = '';
    if (ctx.full) document.querySelector('.dlg.mwin').classList.add('dsfull');
    // the 3D stage
    if (window.Garage && car) {
      if (!ctx.st || !ctx.st.alive) ctx.st = window.Garage.studio($('#dsStage'), null, { yaw: -0.6, bg: ctx.bg || 'white', pixel: { low: 0.6, mid: 1, high: 2 }[O.gfx] || 1, fit: 1.3 });
      else ctx.st.mount($('#dsStage'));
      for (const [k, v] of Object.entries(ctx.st.ctl)) { const b = document.querySelector(`#dsStage .carctl [data-ctl="${k}"]`); if (b && b.tagName === 'BUTTON') { b.classList.toggle('on', !!v); b.setAttribute('aria-pressed', v ? 'true' : 'false'); } }
      const sr = document.querySelector('#dsStage .carctl input[data-ctl=steer]'); if (sr) { sr.value = -(ctx.st.ctl.steer || 0); sr.nextElementSibling.textContent = `${Math.abs(sr.value)}°`; }
      ctx.st.set(carSpec(ctx.keepView));
      ctx.keepView = false;
      window.Garage.bindCtl($('#dsStage'), ctx.st.ctl, (f) => { ctx.ctlFolded = f; });
    }
    bind();
  };
  // music
  if (!ctx.music) {
    ctx.music = 'loading';
    window.odc.models([], false, 'visualshop').then((r) => {
      if (!r || !r.music || ctx.music !== 'loading') { ctx.music = null; return; }
      const url = URL.createObjectURL(new Blob([r.music], { type: 'audio/mpeg' }));
      const a = new Audio(url); a.loop = true; a.volume = shopOpts().music / 100; a.play().catch(() => {});
      ctx.music = a;
    }).catch(() => { ctx.music = null; });
  }
  const cleanup = () => {
    if (ctx.st) { ctx.st.dispose(); ctx.st = null; }
    if (ctx.music && ctx.music.pause) { ctx.music.pause(); URL.revokeObjectURL(ctx.music.src); }
    ctx.music = null;
    clearInterval(ctx.watch);
  };
  const redrawKeep = () => { ctx.keepView = true; ctx.cleanup = null; draw(); ctx.cleanup = cleanup; };
  const bind = () => {
    $$('[data-tab]').forEach((b) => b.onclick = () => { ctx.tab = b.dataset.tab; ctx.sub = null; ctx.page = 0; redraw(); });
    $$('[data-sub]').forEach((b) => b.onclick = () => { ctx.sub = b.dataset.sub || null; ctx.page = 0; redraw(); });
    if ($('#shQ')) $('#shQ').onchange = (e) => { ctx.q = e.target.value; ctx.page = 0; redraw(); };
    if ($('#dsPgL')) $('#dsPgL').onclick = () => { ctx.page--; redraw(); };
    if ($('#dsPgR')) $('#dsPgR').onclick = () => { ctx.page++; redraw(); };
    $$('[data-it]').forEach((b) => b.onclick = (e) => {
      if (e.target.closest('[data-buy]')) return;
      const it = byUid.get(b.dataset.it);
      ctx.sel = it.uid;
      if ((it.cat >= 1 && it.cat <= 13) || [32, 38, 47, 48, 52].includes(it.cat)) {
        const slot = SLOT(it.cat);
        if (ctx.cart.has(slot) && ctx.cart.get(slot).uid === it.uid) ctx.cart.delete(slot);
        else ctx.cart.set(slot, { uid: it.uid, opt: optionsOf(it)[0] || null, p: 0 });
      }
      redraw();
    });
    $$('[data-opt]').forEach((b) => b.onclick = () => {
      const it = sel; const slot = SLOT(it.cat);
      const o = optionsOf(it).find((x) => x.key === b.dataset.opt);
      ctx.cart.set(slot, Object.assign({ uid: it.uid, p: 0 }, ctx.cart.get(slot) || {}, { opt: o }));
      redraw();
    });
    $$('[data-rm]').forEach((b) => b.onclick = () => { ctx.cart.delete(b.dataset.rm); redraw(); });
    // the colour window (paint, neon, glass): saturation / value square and hue bar, as the game's
    if ($('#dsSV')) {
      const sv = $('#dsSV');
      const pick = (e) => {
        const r = sv.getBoundingClientRect();
        const S = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), V = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
        const h = (ctx.hue || 0) / 60, c = V * S, xx = c * (1 - Math.abs((h % 2) - 1)), m = V - c;
        const [r1, g1, b1] = h < 1 ? [c, xx, 0] : h < 2 ? [xx, c, 0] : h < 3 ? [0, c, xx] : h < 4 ? [0, xx, c] : h < 5 ? [xx, 0, c] : [c, 0, xx];
        const rgb = (Math.round((r1 + m) * 255) << 16) | (Math.round((g1 + m) * 255) << 8) | Math.round((b1 + m) * 255);
        const slot = SLOT(sel.cat);
        ctx.cart.set(slot, Object.assign({}, ctx.cart.get(slot), { rgb }));
        redraw();
      };
      sv.onclick = pick;
      $('#dsHue').onchange = (e) => { ctx.hue = Number(e.target.value); sv.style.backgroundColor = `hsl(${ctx.hue},100%,50%)`; };
      $('#dsHue').oninput = (e) => { sv.style.backgroundColor = `hsl(${e.target.value},100%,50%)`; };
    }
    if ($('#dsPlate')) {
      const inp = $('#dsPlate'); let tm = 0;
      inp.oninput = () => {
        const v = plateText(inp.value); if (v !== inp.value) inp.value = v;
        const slot = SLOT(sel.cat); ctx.cart.set(slot, Object.assign({}, ctx.cart.get(slot), { text: v }));
        clearTimeout(tm); tm = setTimeout(() => { if (ctx.st && ctx.st.alive && car) ctx.st.set(carSpec(true)); }, 250);
      };
    }
    $('#dsDef').onclick = () => { ctx.cart.clear(); redraw(); };
    if ($('#dsPrevCar')) $('#dsPrevCar').onclick = () => { ctx.carIx = (ctx.carIx - 1 + d.cars.length) % d.cars.length; ctx.cart.clear(); redraw(); };
    if ($('#dsNextCar')) $('#dsNextCar').onclick = () => { ctx.carIx = (ctx.carIx + 1) % d.cars.length; ctx.cart.clear(); redraw(); };
    const full = (on) => { ctx.full = on; document.querySelector('.dlg.mwin').classList.toggle('dsfull', on); };
    $('#dsFull').onclick = () => full(true);
    $('#dsExit').onclick = () => full(false);
    $('#dsScene').onclick = () => { ctx.bg = ctx.bg === 'garage' ? 'white' : 'garage'; if (ctx.st) ctx.st.scene(ctx.bg); $('#dsScene').textContent = ctx.bg === 'garage' ? '◻' : '🏠'; $('#dsStage').classList.toggle('garage', ctx.bg === 'garage'); };
    $('#dsStage').classList.toggle('garage', ctx.bg === 'garage');
    $('#dsOpt').onclick = () => { const p = $('#dsOptPanel'); p.hidden = !p.hidden; };
    $$('[data-gfx]').forEach((b) => b.onclick = () => { O.gfx = b.dataset.gfx; if (window.Garage) window.Garage.gfxSet(O.gfx); $$('[data-gfx]').forEach((x) => x.classList.toggle('on', x === b)); });
    $('#dsVol').oninput = (e) => { O.music = Number(e.target.value); saveShopOpts(O); e.target.nextElementSibling.textContent = O.music + '%'; if (ctx.music && ctx.music.pause) ctx.music.volume = O.music / 100; };
    const buy = async (list) => {
      const done = [];
      for (const x of list) {
        const it = byUid.get(x.uid); const p = it.prices[x.p || 0];
        try {
          await moreApi(ctx, 'shop_buy', { uid: it.uid, days: p.days, cur: p.cc ? 'cc' : 'mito', car: car.id, text: textOf(it, x.opt, x) });
          done.push(it.name);
        } catch (e) { ctx.msg = badMsg(`${it.name}: ${errText(e)}`); break; }
      }
      if (done.length) { ctx.msg = (ctx.msg ? ctx.msg + ' ' : '') + okMsg(t('shBought', { n: done.join(', ') })); ctx.reload = true; }
      ctx.shop = await moreLoad(ctx, 'shop'); ctx.shopCid = ctx.cid; ctx.reload = false; ctx.cart = new Map();
      ctx.cleanup = null; ctx.keepView = true;
      ctx.redraw();
    };
    // the checkout window (as the game's): every item chosen, each with its period (the prices of its shop row:
    // 7 / 30 / 90 / 365 days or for good, Mito or CC), the totals, then Purchase
    const dayTxt = (p) => (p.days ? t('dsDays', { n: p.days }) : T.dsForever);
    const checkout = (list) => {
      const rows = list.map((x) => Object.assign({}, x, { p: x.p || 0 }));
      const box = document.createElement('div');
      box.className = 'dsco'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'true'); box.setAttribute('aria-label', T.dsCheckout);
      const paint = () => {
        let m = 0, c = 0;
        for (const x of rows) { const p = byUid.get(x.uid).prices[x.p]; m += p.mito || 0; c += p.cc || 0; }
        box.innerHTML = `<div class="dscoin"><h3>${esc(T.dsCheckout)}</h3>
          <div class="dscolist">${rows.map((x, k) => { const it = byUid.get(x.uid); return `<div class="dscorow">${icon(it.id)}
            <div class="dsconame"><b>${esc(it.name)}</b>${x.opt ? `<small>${esc(x.opt.label)}</small>` : ''}</div>
            <select data-cop="${k}" aria-label="${esc(T.dsPeriod)}">${it.prices.map((p, j) => `<option value="${j}" ${j === x.p ? 'selected' : ''}>${esc(dayTxt(p))} — ${p.cc ? N(p.cc) + ' CC' : N(p.mito) + ' Mito'}</option>`).join('')}</select>
            <button class="dsrm" data-cox="${k}" aria-label="✕">✕</button></div>`; }).join('') || `<div class="muted small">${esc(T.cNone)}</div>`}</div>
          <div class="dscotot">${esc(T.dsTotal)} ${m ? `<b class="mi">Ⓜ ${N(m)}</b>` : ''}${c ? `<b class="cc">◉ ${N(c)}</b>` : ''}${!m && !c ? '<b>0</b>' : ''}
            <span class="muted small">${esc(T.shMito)} ${N(ctx.mito)} · ${esc(T.shCC)} ${N(ctx.cc)}</span></div>
          <div class="dscobtn"><button class="dsbuyall" id="dsCoOk" ${rows.length ? '' : 'disabled'}>↵ ${esc(T.dsPurchase)}</button><button class="btn" id="dsCoNo">${esc(T.cancel || 'Cancelar')}</button></div></div>`;
        box.querySelectorAll('[data-cop]').forEach((el) => el.onchange = () => { rows[Number(el.dataset.cop)].p = Number(el.value); paint(); });
        box.querySelectorAll('[data-cox]').forEach((el) => el.onclick = () => { rows.splice(Number(el.dataset.cox), 1); paint(); });
        box.querySelector('#dsCoNo').onclick = () => box.remove();
        box.querySelector('#dsCoOk').onclick = () => {
          box.remove();
          for (const x of rows) { const slot = SLOT(byUid.get(x.uid).cat); const c2 = ctx.cart.get(slot); if (c2 && c2.uid === x.uid) c2.p = x.p; }
          buy(rows);
        };
      };
      paint();
      document.querySelector('.dsbody').appendChild(box);
      box.querySelector('select, button').focus();
    };
    $$('[data-buy]').forEach((b) => b.onclick = () => {
      const it = byUid.get(b.dataset.buy);
      const inCart = ctx.cart.get(SLOT(it.cat));
      checkout([inCart && inCart.uid === it.uid ? inCart : { uid: it.uid, opt: optionsOf(it)[0] || null, p: 0 }]);
    });
    $('#dsBuyAll').onclick = () => checkout([...ctx.cart.values()]);
  };
  const redraw = () => { ctx.keepView = true; ctx.redraw(); };
  // the first draw of this page: the stage and the music of a previous draw (another runner) stay
  { const cl = ctx.cleanup; ctx.cleanup = null; if (cl && cl !== cleanup && !ctx.st) cl(); }
  draw();
  ctx.cleanup = cleanup;
  clearInterval(ctx.watch);
  ctx.watch = setInterval(() => { if (!document.querySelector('.dsbody')) { const c = ctx.cleanup; if (c === cleanup) { ctx.cleanup = null; c(); } else clearInterval(ctx.watch); } }, 800);
  // the pictures: item icons of the page, the car name logo
  const want = [...shown.slice(ctx.page * PER, ctx.page * PER + PER).map((i) => 'item:' + i.id.toLowerCase()), ...[...ctx.cart.values()].map((x) => 'item:' + byUid.get(x.uid).id.toLowerCase()),
    ...(sel ? optionsOf(sel).filter((o) => o.icon).map((o) => 'item:' + o.icon.toLowerCase()) : []), car ? 'logo:' + car.model : ''];
  loadIcons(want.filter(Boolean)).then((ch) => { if (ch && document.querySelector('.dsbody')) redraw(); });
};

// ---------------------------------------------------------------- Gotcha
const GOTCHA_CARS = [[440, 'Dominator'], [432, 'Hykan'], [429, 'Prometheus'], [425, 'GRAVITY'], [421, 'PLUCK'], [417, 'Honour'], [414, 'Pandora']];
MORE_PAGES.gotcha = async (ctx) => {
  ctx.machine = ctx.machine || 'cc';
  const cc = ctx.machine === 'cc';
  const info = (await moreLoad(ctx, 'gotcha_info', { machine: ctx.machine })) || { slots: [], price: cc ? 300 : 50000 };
  const other = ctx.otherPrice || (cc ? 50000 : 300);
  const prices = cc ? [info.price, other] : [other, info.price];
  const balls = Array.from({ length: 14 }, (_, i) => `<i class="gball b${i % 4}" style="left:${8 + ((i * 37) % 80)}%;top:${10 + ((i * 53) % 62)}%;animation-delay:${(i % 5) * -0.13}s"></i>`).join('');
  ctx.frame(`<div class="mgot"><div class="gstage" id="gStage">
      <div class="gmachine"><div class="gdome">${balls}<b class="glogo">${esc(T.gTitle)}</b></div><div class="gbase"><span class="gknob"></span><span class="gknob"></span><span class="gchute" id="gChute"></span></div></div>
      <div class="gmach"><button class="gmc${cc ? ' on' : ''} cc" data-mach="cc"><small>${esc(T.gSelCC)}</small><span class="ring"></span><b>${esc(T.gCC)}</b></button>
        <button class="gmc${!cc ? ' on' : ''} mi" data-mach="mito"><small>${esc(T.gSelMito)}</small><span class="ring"></span><b>${esc(T.gMito)}</b></button></div>
      <button class="gspin" id="gSpin">${esc(t('gSpin', { n: ctx.cname || '' }))}</button>
      <div class="mfoot gmsg">${ctx.msg || ''}</div><div class="gflash" id="gFlash"></div><div class="gwin" id="gWin" hidden></div></div>
    <div class="gside"><div class="ghead"><span class="gcoin">${cc ? 'COIN' : 'MITO'}</span><b>${esc(cc ? T.gCC : T.gMito)}</b></div>
      ${GOTCHA_CARS.map(([id], k) => {
        const sl = info.slots[k];
        const lines = sl ? sl.cars.map((c) => `${c.name} (V1): ${Math.round((c.chance * sl.chance) / info.total)}%`) : [];
        return `<div class="gslot"${sl ? Tip.attr({ name: sl.text.split('\n')[0], desc: sl.text.split('\n').slice(1).join('\n'), lines: [T.gChances, ...lines] }) : ''}><img src="assets/gotcha/got_${id}.png" alt=""><span class="gtag">${cc ? '<em class="b">BT</em>/<em class="s">ST</em>' : '<em class="n">NT</em>/<em class="b">BT</em>'}</span></div>`;
      }).join('')}
      <div class="gpage"><button class="garr" disabled>◀</button><span>1 <i>/</i> 1</span><button class="garr" disabled>▶</button></div></div></div>
    <div class="gbar"><span>${esc(T.gMyCC)}<b class="cc">${N(ctx.cc)}</b></span><span>${esc(T.gMyMito)}<b class="mi">${N(ctx.mito)}</b></span>
      <span>${esc(T.gCostCC)}<b class="cc">${N(prices[0])} Coin</b></span><span>${esc(T.gCostMito)}<b class="mi">${N(prices[1])} Mito</b></span></div>`, T.mSubGot);
  ctx.msg = '';
  ctx.otherPrice = null;
  $$('[data-mach]').forEach((b) => b.onclick = () => { if (b.dataset.mach !== ctx.machine) { ctx.otherPrice = info.price; ctx.machine = b.dataset.mach; ctx.redraw(); } });
  let pv = null;
  ctx.cleanup = () => { if (pv) pv.dispose(); };
  const showWin = (r) => {
    const box = $('#gWin');
    const car = (r.won.find((w) => w.car) || {}).car;
    const pts = r.won.filter((w) => !w.car);
    box.innerHTML = `<div class="gwin-in"><div class="gcongr">${esc(T.gCongrats)}</div>
      <div class="gwname">${car ? `${esc(car.name)} <span>V1</span>` : esc(pts.map((w) => `${w.name} ×${w.count}`).join(', '))}</div>
      ${car ? '<div class="gw3d" id="gW3d"></div>' : `<div class="gwpts">${pts.map((w) => itemPic(w.id, 'gwi')).join('')}</div>`}
      <div class="small gwnote">${esc(car ? T.gBoxNote : T.gPointsNote)}</div>
      <button class="gspin" id="gOk">OK</button></div>`;
    box.hidden = false;
    if (car && window.Garage) pv = window.Garage.preview($('#gW3d'), car, { yaw: -0.5 });
    $('#gOk').onclick = () => { if (pv) { pv.dispose(); pv = null; } box.hidden = true; ctx.redraw(); };
  };
  $('#gSpin').onclick = async () => {
    const st = $('#gStage');
    $('#gSpin').disabled = true; $$('[data-mach]').forEach((b) => { b.disabled = true; });
    let r;
    try { r = await moreApi(ctx, 'gotcha', { machine: ctx.machine }); } catch (e) {
      $('.gmsg').innerHTML = badMsg(e); $('#gSpin').disabled = false; $$('[data-mach]').forEach((b) => { b.disabled = false; }); return;
    }
    loadIcons(r.won.map((w) => 'item:' + w.id.toLowerCase()));
    // the spin, after the game's: the coins drop in, the machine shakes and turns its knobs, a capsule falls out and
    // opens in a burst of light; then the prize
    const fx = document.createElement('div');
    fx.className = 'gfx';
    fx.innerHTML = '<i class="gcoin1"></i><i class="gcoin2"></i><i class="gcoin3"></i><div class="gcap"><b class="top"></b><b class="bot"></b></div><div class="grays"></div>';
    st.appendChild(fx);
    const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
    st.classList.add('coins'); await wait(900);
    st.classList.add('spin'); await wait(1700);
    st.classList.add('drop'); await wait(900);
    st.classList.add('open'); await wait(700);
    st.classList.add('flash'); await wait(300);
    showWin(r);
    setTimeout(() => { st.classList.remove('flash', 'coins', 'spin', 'drop', 'open'); fx.remove(); }, 700);
  };
};
