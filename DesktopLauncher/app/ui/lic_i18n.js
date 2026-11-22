'use strict';
/* License.xlt is in English only: its names, descriptions, effects and conditions in Portuguese and Russian.
   Lines are translated by the templates below (the many numbered variants) or by the phrase table; place names,
   mission names and badge names stay as the game writes them. window.licText(text, lang) -> the text. */
(function () {
  const CITY = { pt: (c) => c, ru: (c) => c };
  const P = {
    pt: {
      'Rookie': 'Novato', 'Challenger': 'Desafiante', 'Class A': 'Classe A', 'Class AA': 'Classe AA', 'Class AAA': 'Classe AAA', 'Class B': 'Classe B',
      'Class C': 'Classe C', 'Class D': 'Classe D', 'Class E': 'Classe E', 'Auction Master': 'Mestre do Leilão', 'Daily Mission Master': 'Mestre das Missões Diárias',
      'Daily Mission Master License': 'Licença de Mestre das Missões Diárias', 'Delivery Master': 'Mestre das Entregas', 'Delivery Master License': 'Licença de Mestre das Entregas',
      'Delivery Medalist License': 'Licença de Medalhista de Entregas', 'Delivery Service EX Medalist License': 'Licença de Medalhista do Delivery Service EX',
      'DCGP Win': 'Vitória no DCGP', 'DCGP victory in last season': 'Vitória no DCGP da última temporada', 'Guardian': 'Guardião', 'Guardian License Acquired.': 'Licença de Guardião obtida.',
      'Fearless Channel Battle Challenger License': 'Licença de Desafiante Destemido da Batalha de Canal', 'Gotcha DC Character Badge Collector 1': 'Colecionador de Emblemas de Personagem DC da Gotcha 1',
      'Ind. Battle Master': 'Mestre da Batalha Individual', 'Ind. Battle Pro': 'Pro da Batalha Individual', 'Ind. Battle Semi Pro': 'Semi Pro da Batalha Individual',
      'Team Battle Master': 'Mestre da Batalha em Equipe', 'Team Battle Pro': 'Pro da Batalha em Equipe', 'Team Battle Semi Pro': 'Semi Pro da Batalha em Equipe',
      'Beginner HUV Hunter License': 'Licença de Caçador de HUV Iniciante', 'Intermediate HUV Hunter License': 'Licença de Caçador de HUV Intermediário',
      'Advanced HUV Hunter License': 'Licença de Caçador de HUV Avançado', 'Master HUV Hunter License': 'Licença de Caçador de HUV Mestre', 'Advanced Patrolee License': 'Licença de Patrulheiro Avançado',
      'HUV Hunter Master': 'Caçador de HUV Mestre', 'HUV Hunter Master License Acquired.': 'Licença de Caçador de HUV Mestre obtida.',
      'HUV Hunter Grade A': 'Caçador de HUV Grau A', 'HUV Hunter Grade B': 'Caçador de HUV Grau B', 'HUV Hunter Grade C': 'Caçador de HUV Grau C',
      'Joined in OMD': 'Entrou na OMD', 'Joined in ROO': 'Entrou na ROO', 'OMD Special': 'OMD Especial', 'ROO Special': 'ROO Especial',
      'Koinonia Quest Completed': 'Quest de Koinonia concluída', 'Moon Palace Quest Completed': 'Quest de Moon Palace concluída', 'Oros Quest Completed': 'Quest de Oros concluída',
      'License Issued if any one of the above criteria is fulfilled': 'A licença é dada se qualquer um dos critérios acima for cumprido',
      'Main Quest Complete': 'Quest principal concluída', 'Main Quest Completed': 'Quest principal concluída', 'Mafia Reputation License': 'Licença de Reputação da Máfia',
      'Master Auctioneer License': 'Licença de Mestre Leiloeiro', 'Master Channel Battle Defender License': 'Licença de Mestre Defensor da Batalha de Canal',
      'Mitro Airport Base Reputation License': 'Licença de Reputação da Base Aérea de Mitro', 'Mitro City Hall Reputation License': 'Licença de Reputação da Prefeitura de Mitro',
      'Mittron Island Guardian': 'Guardião da Ilha Mittron', 'Neo City Chapter 1 Clear': 'Neo City Capítulo 1 concluído', 'Neo City Chapter 1 Clear License': 'Licença de Neo City Capítulo 1 concluído',
      'Neo City Class C': 'Neo City Classe C', 'No Bonus Effect': 'Sem efeito bônus', 'No.9': 'Nº 9', 'Number Nine License Acquired.': 'Licença Número Nove obtida.', 'Overkill': 'Overkill',
      'Parts Enhancing Master License': 'Licença de Mestre do Aprimoramento de Peças', 'Parts Meister License': 'Licença de Meister de Peças', 'Patrol Master License': 'Licença de Mestre da Patrulha',
      'Pro Camouflage': 'Camuflagem Pro', 'Pro Camouflage of traffic car and HUV License': 'Licença de Camuflagem Pro de carros de trânsito e HUV', 'Production Meistser License': 'Licença de Meister da Fabricação',
      'Quest Master': 'Mestre das Quests', 'Quest Master License': 'Licença de Mestre das Quests', 'Quest Master License Acquired.': 'Licença de Mestre das Quests obtida.',
      'Special Patrol': 'Patrulha Especial', 'Tuning Master': 'Mestre do Tuning', 'Tuning Master License Acquired.': 'Licença de Mestre do Tuning obtida.',
      'Undercity Guardian': 'Guardião da Undercity', 'Undercity Guardian License': 'Licença de Guardião da Undercity', 'Undercity Guardian License Acquired.': 'Licença de Guardião da Undercity obtida.',
      'Underground': 'Underground', 'Veteran Patrol': 'Patrulha Veterana', 'Veteran Patrol License Acquired.': 'Licença de Patrulha Veterana obtida.', 'Auction Master License Acquired.': 'Licença de Mestre do Leilão obtida.',
      'Attain Reputation Points from the Corresponding Group': 'Conseguir pontos de reputação no grupo correspondente',
      'Destroy the 1000 NEO HUVs in NEO cities!': 'Destrua 1000 NEO HUVs nas cidades NEO!',
      '10% discount on Auction Fees': '10% de desconto nas taxas do leilão', '50% Discount on Auction House Commision': '50% de desconto na comissão do leilão',
      '50% discount on Enhancement Fees': '50% de desconto nas taxas de aprimoramento', '8% EXP and Mito Reward': '+8% de EXP e Mito de recompensa',
      '5% increase in EXP and Mito Received from Undercity': '+5% de EXP e Mito recebidos na Undercity', 'Camouflage Kit and Mitto +5%': 'Kit de camuflagem e Mito +5%',
      'A Master Token for Parts Modify and Convert': 'Um token de mestre para modificar e converter peças', 'A Master Token for Production': 'Um token de mestre para fabricação',
      'A bunch of Convert Chace Increasing Liquid (99 counts)': 'Um lote de líquido que aumenta a chance de conversão (99 unidades)',
      'Raise Parts Chance Gauge Recharging Rate by 2x': 'Recarga da barra de chance de peças 2x mais rápida', 'Raise the basic production success rate by +15%': 'Chance base de sucesso na fabricação +15%',
      '5% increase in the amouint of exp points and Mito obtained / car endurance 2% healed when driving against traffic (Battle Only)': '+5% de EXP e Mito recebidos / recupera 2% da resistência do carro ao dirigir na contramão (só em batalha)',
      'License issed to symbolize the best driver of the field.': 'Licença que simboliza o melhor piloto do campo.', 'License issued to symbolize the best driver in DC': 'Licença que simboliza o melhor piloto do DC',
      'License issued to symbolize the best driver who helped the most in keeping the peace of Mittron Island': 'Licença que simboliza o piloto que mais ajudou a manter a paz na Ilha Mittron',
      'This is a License for those that collect the complete first set of DC Character Badges that are available to obtain via Gotcha.': 'Licença para quem completa o primeiro conjunto de Emblemas de Personagem DC que saem na Gotcha.',
      'This is a driver’s license given by each city for gold medalists who have won a certain Delivery Service EX match.': 'Licença dada por cada cidade aos medalhistas de ouro de uma partida do Delivery Service EX.',
      'A license to reward the drivers who is learning to earn all the medals from all delivery missions.': 'Licença que premia quem está conquistando todas as medalhas das missões de entrega.',
      'When the receiving license ""DCPG Win': 'Ao receber a licença "Vitória no DCGP"', 'Total Camouflage Time %d / 720000 초': 'Tempo total de camuflagem %d / 720000 s',
      'Field Driving Hours %d / 180000 secs': 'Tempo dirigindo no campo %d / 180000 s',
      'Cras Chase success count %d / 40                                               Cras Quest Completed': 'Perseguições concluídas em Cras %d / 40\nQuest de Cras concluída',
    },
    ru: {
      'Rookie': 'Новичок', 'Challenger': 'Претендент', 'Class A': 'Класс A', 'Class AA': 'Класс AA', 'Class AAA': 'Класс AAA', 'Class B': 'Класс B', 'Class C': 'Класс C',
      'Class D': 'Класс D', 'Class E': 'Класс E', 'Auction Master': 'Мастер аукциона', 'Daily Mission Master': 'Мастер ежедневных миссий', 'Daily Mission Master License': 'Лицензия мастера ежедневных миссий',
      'Delivery Master': 'Мастер доставки', 'Delivery Master License': 'Лицензия мастера доставки', 'Delivery Medalist License': 'Лицензия медалиста доставки',
      'Delivery Service EX Medalist License': 'Лицензия медалиста Delivery Service EX', 'DCGP Win': 'Победа в DCGP', 'DCGP victory in last season': 'Победа в DCGP прошлого сезона',
      'Guardian': 'Страж', 'Guardian License Acquired.': 'Получена лицензия стража.', 'Fearless Channel Battle Challenger License': 'Лицензия бесстрашного претендента битвы каналов',
      'Gotcha DC Character Badge Collector 1': 'Коллекционер значков персонажей DC из Gotcha 1', 'Ind. Battle Master': 'Мастер одиночной битвы', 'Ind. Battle Pro': 'Профи одиночной битвы',
      'Ind. Battle Semi Pro': 'Полупрофи одиночной битвы', 'Team Battle Master': 'Мастер командной битвы', 'Team Battle Pro': 'Профи командной битвы', 'Team Battle Semi Pro': 'Полупрофи командной битвы',
      'Beginner HUV Hunter License': 'Лицензия начинающего охотника на HUV', 'Intermediate HUV Hunter License': 'Лицензия опытного охотника на HUV', 'Advanced HUV Hunter License': 'Лицензия продвинутого охотника на HUV',
      'Master HUV Hunter License': 'Лицензия мастера-охотника на HUV', 'Advanced Patrolee License': 'Лицензия продвинутого патрульного', 'HUV Hunter Master': 'Мастер-охотник на HUV',
      'HUV Hunter Master License Acquired.': 'Получена лицензия мастера-охотника на HUV.', 'HUV Hunter Grade A': 'Охотник на HUV класса A', 'HUV Hunter Grade B': 'Охотник на HUV класса B', 'HUV Hunter Grade C': 'Охотник на HUV класса C',
      'Joined in OMD': 'Вступил в OMD', 'Joined in ROO': 'Вступил в ROO', 'OMD Special': 'Особый OMD', 'ROO Special': 'Особый ROO', 'Koinonia Quest Completed': 'Квест Koinonia выполнен',
      'Moon Palace Quest Completed': 'Квест Moon Palace выполнен', 'Oros Quest Completed': 'Квест Oros выполнен', 'License Issued if any one of the above criteria is fulfilled': 'Лицензия выдаётся при выполнении любого из условий выше',
      'Main Quest Complete': 'Основной квест выполнен', 'Main Quest Completed': 'Основной квест выполнен', 'Mafia Reputation License': 'Лицензия репутации у мафии', 'Master Auctioneer License': 'Лицензия мастера-аукциониста',
      'Master Channel Battle Defender License': 'Лицензия мастера-защитника битвы каналов', 'Mitro Airport Base Reputation License': 'Лицензия репутации на авиабазе Mitro', 'Mitro City Hall Reputation License': 'Лицензия репутации в мэрии Mitro',
      'Mittron Island Guardian': 'Страж острова Mittron', 'Neo City Chapter 1 Clear': 'Neo City: глава 1 пройдена', 'Neo City Chapter 1 Clear License': 'Лицензия: Neo City, глава 1 пройдена', 'Neo City Class C': 'Neo City класс C',
      'No Bonus Effect': 'Без бонуса', 'No.9': '№ 9', 'Number Nine License Acquired.': 'Получена лицензия «Номер девять».', 'Overkill': 'Overkill', 'Parts Enhancing Master License': 'Лицензия мастера улучшения деталей',
      'Parts Meister License': 'Лицензия мейстера деталей', 'Patrol Master License': 'Лицензия мастера патруля', 'Pro Camouflage': 'Профи маскировки', 'Pro Camouflage of traffic car and HUV License': 'Лицензия профи маскировки под трафик и HUV',
      'Production Meistser License': 'Лицензия мейстера производства', 'Quest Master': 'Мастер квестов', 'Quest Master License': 'Лицензия мастера квестов', 'Quest Master License Acquired.': 'Получена лицензия мастера квестов.',
      'Special Patrol': 'Особый патруль', 'Tuning Master': 'Мастер тюнинга', 'Tuning Master License Acquired.': 'Получена лицензия мастера тюнинга.', 'Undercity Guardian': 'Страж Undercity',
      'Undercity Guardian License': 'Лицензия стража Undercity', 'Undercity Guardian License Acquired.': 'Получена лицензия стража Undercity.', 'Underground': 'Underground', 'Veteran Patrol': 'Ветеран патруля',
      'Veteran Patrol License Acquired.': 'Получена лицензия ветерана патруля.', 'Auction Master License Acquired.': 'Получена лицензия мастера аукциона.', 'Attain Reputation Points from the Corresponding Group': 'Наберите очки репутации у соответствующей группы',
      'Destroy the 1000 NEO HUVs in NEO cities!': 'Уничтожьте 1000 NEO HUV в городах NEO!', '10% discount on Auction Fees': 'Скидка 10% на сборы аукциона', '50% Discount on Auction House Commision': 'Скидка 50% на комиссию аукциона',
      '50% discount on Enhancement Fees': 'Скидка 50% на стоимость улучшения', '8% EXP and Mito Reward': '+8% к опыту и Mito в награде', '5% increase in EXP and Mito Received from Undercity': '+5% к опыту и Mito в Undercity',
      'Camouflage Kit and Mitto +5%': 'Набор маскировки и Mito +5%', 'A Master Token for Parts Modify and Convert': 'Мастер-жетон для модификации и конвертации деталей', 'A Master Token for Production': 'Мастер-жетон для производства',
      'A bunch of Convert Chace Increasing Liquid (99 counts)': 'Набор жидкости, повышающей шанс конвертации (99 шт.)', 'Raise Parts Chance Gauge Recharging Rate by 2x': 'Шкала шанса деталей заряжается в 2 раза быстрее',
      'Raise the basic production success rate by +15%': 'Базовый шанс успеха производства +15%',
      '5% increase in the amouint of exp points and Mito obtained / car endurance 2% healed when driving against traffic (Battle Only)': '+5% к опыту и Mito / езда по встречной восстанавливает 2% прочности машины (только в битве)',
      'License issed to symbolize the best driver of the field.': 'Лицензия лучшего гонщика поля.', 'License issued to symbolize the best driver in DC': 'Лицензия лучшего гонщика DC',
      'License issued to symbolize the best driver who helped the most in keeping the peace of Mittron Island': 'Лицензия гонщика, больше всех помогавшего хранить мир на острове Mittron',
      'This is a License for those that collect the complete first set of DC Character Badges that are available to obtain via Gotcha.': 'Лицензия для тех, кто собрал первый полный набор значков персонажей DC из Gotcha.',
      'This is a driver’s license given by each city for gold medalists who have won a certain Delivery Service EX match.': 'Лицензия, которую каждый город выдаёт золотым медалистам матча Delivery Service EX.',
      'A license to reward the drivers who is learning to earn all the medals from all delivery missions.': 'Лицензия для гонщиков, собирающих все медали миссий доставки.',
      'When the receiving license ""DCPG Win': 'При получении лицензии «Победа в DCGP»', 'Total Camouflage Time %d / 720000 초': 'Общее время маскировки %d / 720000 с', 'Field Driving Hours %d / 180000 secs': 'Время езды по полю %d / 180000 с',
      'Cras Chase success count %d / 40                                               Cras Quest Completed': 'Успешные погони в Cras %d / 40\nКвест Cras выполнен',
    },
  };
  // counters: "<what> %d / N"
  const COUNT = {
    pt: { 'HUV Success Count': 'HUV concluídos', 'Rushtime Success Count': 'Rush Time concluídos', 'Rushtime Lucky Driver Achievement Count': 'Vezes como piloto sortudo do Rush Time',
      'Normal Patrol Success Count': 'Patrulhas normais concluídas', 'Party Patrol Success Count': 'Patrulhas em grupo concluídas', 'Repeatable Quest Success Count': 'Quests repetíveis concluídas',
      'Undercity Success Count': 'Undercity concluídas', 'Delivery Play Count': 'Entregas jogadas', 'Mission Token Count': 'Tokens de missão', 'Channel Battle Attack Count': 'Ataques na Batalha de Canal',
      'Channel Battle Defend Count': 'Defesas na Batalha de Canal', 'Delivery Bronze Medal Count': 'Medalhas de bronze em entregas', 'Delivery Silver Medal Count': 'Medalhas de prata em entregas',
      'Delivery Gold Medal Count': 'Medalhas de ouro em entregas', 'Battle Zone Team Game Counts': 'Partidas em equipe na Battle Zone', 'Battle Zone individual Game Counts': 'Partidas individuais na Battle Zone',
      'Ind. Battle Count': 'Batalhas individuais', 'Team Battle Count': 'Batalhas em equipe', 'NEO HUV destroyed': 'NEO HUV destruídos', 'Cras Patrol success count': 'Patrulhas concluídas em Cras',
      'Monthly Item Production Effort count': 'Fabricações de itens no mês', 'Monthly Parts Convert Effot count': 'Conversões de peças no mês', 'Monthly Parts Modify Effort count': 'Modificações de peças no mês',
      '+15 or Higher Level Parts Enhancement Count': 'Aprimoramentos de peças +15 ou mais', '+19 or Higher Level Parts Enhancement Count': 'Aprimoramentos de peças +19 ou mais',
      '20k Mito or Higher Item Auction Registeration Count': 'Itens de 20 mil Mito ou mais anunciados no leilão', '20k Mito or Higher Item Auction Sold Count': 'Itens de 20 mil Mito ou mais vendidos no leilão' },
    ru: { 'HUV Success Count': 'Успешные HUV', 'Rushtime Success Count': 'Успешные Rush Time', 'Rushtime Lucky Driver Achievement Count': 'Раз счастливым гонщиком Rush Time',
      'Normal Patrol Success Count': 'Успешные обычные патрули', 'Party Patrol Success Count': 'Успешные групповые патрули', 'Repeatable Quest Success Count': 'Выполненные повторяемые квесты',
      'Undercity Success Count': 'Успешные Undercity', 'Delivery Play Count': 'Сыграно доставок', 'Mission Token Count': 'Жетоны миссий', 'Channel Battle Attack Count': 'Атаки в битве каналов',
      'Channel Battle Defend Count': 'Защиты в битве каналов', 'Delivery Bronze Medal Count': 'Бронзовые медали доставки', 'Delivery Silver Medal Count': 'Серебряные медали доставки',
      'Delivery Gold Medal Count': 'Золотые медали доставки', 'Battle Zone Team Game Counts': 'Командные игры в Battle Zone', 'Battle Zone individual Game Counts': 'Одиночные игры в Battle Zone',
      'Ind. Battle Count': 'Одиночные битвы', 'Team Battle Count': 'Командные битвы', 'NEO HUV destroyed': 'Уничтожено NEO HUV', 'Cras Patrol success count': 'Успешные патрули в Cras',
      'Monthly Item Production Effort count': 'Производств предметов за месяц', 'Monthly Parts Convert Effot count': 'Конвертаций деталей за месяц', 'Monthly Parts Modify Effort count': 'Модификаций деталей за месяц',
      '+15 or Higher Level Parts Enhancement Count': 'Улучшений деталей до +15 и выше', '+19 or Higher Level Parts Enhancement Count': 'Улучшений деталей до +19 и выше',
      '20k Mito or Higher Item Auction Registeration Count': 'Выставлено на аукцион предметов от 20 тыс. Mito', '20k Mito or Higher Item Auction Sold Count': 'Продано на аукционе предметов от 20 тыс. Mito' },
  };
  // [regex, pt, ru] (functions get the match)
  const TPL = [
    [/^(.+?) Track Play Counts %d ?\/ ?(\d+)$/, (m) => `Partidas nas pistas de ${m[1]} %d / ${m[2]}`, (m) => `Заезды на трассах ${m[1]} %d / ${m[2]}`],
    [/^HUV Cleared in (.+) %d \/ (\d+) Rounds$/, (m) => `HUV concluído em ${m[1]} %d / ${m[2]} rodadas`, (m) => `HUV пройдено в ${m[1]} %d / ${m[2]} раундов`],
    [/^Patrol Cleared in (.+) %d \/ (\d+) Rounds$/, (m) => `Patrulha concluída em ${m[1]} %d / ${m[2]} rodadas`, (m) => `Патруль пройден в ${m[1]} %d / ${m[2]} раундов`],
    [/^Patrol Basic Exp \+(\d+)%$/, (m) => `EXP base da Patrulha +${m[1]}%`, (m) => `Базовый опыт патруля +${m[1]}%`],
    [/^(Amateur|Rookie|Pro|Star|Superstar) Arena Ladder Battle Win Percentage %d%%$/, (m) => `Vitórias no Ladder da Arena ${m[1]} %d%%`, (m) => `Процент побед в Ladder на арене ${m[1]} %d%%`],
    [/^\[([^\]]+)\] (.+?) Gold Medal Acquired\.?$/, (m) => `[${m[1]}] Medalha de ouro obtida: ${m[2]}`, (m) => `[${m[1]}] Получена золотая медаль: ${m[2]}`],
    [/^\[([^\]]+)\] (.+?) Medal Acquired\.?$/, (m) => `[${m[1]}] Medalha obtida: ${m[2]}`, (m) => `[${m[1]}] Получена медаль: ${m[2]}`],
    [/^\[([^\]]+)\] Win a gold medal in (.+)$/, (m) => `[${m[1]}] Ganhe a medalha de ouro em ${m[2]}`, (m) => `[${m[1]}] Получите золотую медаль в ${m[2]}`],
    [/^Obtain “DC Character Badge: (.+)”$/, (m) => `Obter o “Emblema de personagem DC: ${m[1]}”`, (m) => `Получить «Значок персонажа DC: ${m[1]}»`],
    [/^Exp and Mitto for Chase \+(\d+)%$/, (m) => `EXP e Mito na Perseguição +${m[1]}%`, (m) => `Опыт и Mito в погоне +${m[1]}%`],
    [/^Exp and Mitto for Quck Service \+(\d+)%$/, (m) => `EXP e Mito no Quick Service +${m[1]}%`, (m) => `Опыт и Mito в Quick Service +${m[1]}%`],
    [/^Exp and Mitto Drop Rate \+(\d+)%$/, (m) => `EXP e Mito ganhos +${m[1]}%`, (m) => `Получаемые опыт и Mito +${m[1]}%`],
    [/^Parts Drop Rate \+(\d+)%$/, (m) => `Chance de ganhar peças +${m[1]}%`, (m) => `Шанс выпадения деталей +${m[1]}%`],
    [/^Exp for (.+) Quick Service \+(\d+)%$/, (m) => `EXP no Quick Service de ${m[1]} +${m[2]}%`, (m) => `Опыт в Quick Service ${m[1]} +${m[2]}%`],
    [/^Mitto for (.+) Quick Service \+(\d+)%$/, (m) => `Mito no Quick Service de ${m[1]} +${m[2]}%`, (m) => `Mito в Quick Service ${m[1]} +${m[2]}%`],
    [/^(\d+)% increase in Mito received from (Ind\.|Team) Battle$/, (m) => `+${m[1]}% de Mito na Batalha ${m[2] === 'Team' ? 'em Equipe' : 'Individual'}`, (m) => `+${m[1]}% Mito в ${m[2] === 'Team' ? 'командной' : 'одиночной'} битве`],
    [/^(\d+)% increase in (EXP|Mito) received from (.+?) Delivery Missions\.?$/, (m) => `+${m[1]}% de ${m[2]} nas missões de entrega de ${m[3]}`, (m) => `+${m[1]}% ${m[2] === 'EXP' ? 'опыта' : 'Mito'} в миссиях доставки ${m[3]}`],
    [/^After using booster, you can recharge Booster up to 50% with (\d+)% probability \(Battle Exclusive\)$/, (m) => `Depois de usar o booster, ${m[1]}% de chance de recarregá-lo até 50% (só em batalha)`, (m) => `После буста с шансом ${m[1]}% он перезаряжается до 50% (только в битве)`],
    [/^If you acquiring the Contraflow Lane Driving package, it will allow you to recover the vehicle’s durability by 1%\. \(Battle Exclusive\)$/, () => 'Ao pegar o pacote de dirigir na contramão, recupera 1% da resistência do carro (só em batalha)', () => 'Пакет езды по встречной восстанавливает 1% прочности машины (только в битве)'],
    [/^License issued to symbolize (.+)$/, (m) => `Licença que simboliza ${({ 'rookie drivers': 'os pilotos novatos', 'semi-rookie drivers': 'os pilotos quase novatos', 'amateur drivers': 'os pilotos amadores', 'advanced drivers': 'os pilotos avançados', 'semi pro drivers': 'os pilotos semi profissionais', 'pro drivers': 'os pilotos profissionais', 'class AA pro drivers': 'os pilotos profissionais classe AA', 'class AAA pro drivers': 'os pilotos profissionais classe AAA', 'Ind. Battle Masters': 'os mestres da Batalha Individual', 'Ind. Battle Pro Drivers': 'os pilotos pro da Batalha Individual', 'Ind. Battle Semi Pro Drivers': 'os pilotos semi pro da Batalha Individual', 'Team Battle Masters': 'os mestres da Batalha em Equipe', 'Team Battle Pro Drivers': 'os pilotos pro da Batalha em Equipe', 'Team Battle Semi Pro Drivers': 'os pilotos semi pro da Batalha em Equipe', 'OMD Special Ace Drivers': 'os ases especiais da OMD', 'Team ROO Special Ace Drivers': 'os ases especiais da ROO' })[m[1]] || m[1]}`,
      (m) => `Лицензия, символизирующая ${({ 'rookie drivers': 'новичков', 'semi-rookie drivers': 'почти новичков', 'amateur drivers': 'любителей', 'advanced drivers': 'опытных гонщиков', 'semi pro drivers': 'полупрофессионалов', 'pro drivers': 'профессионалов', 'class AA pro drivers': 'профессионалов класса AA', 'class AAA pro drivers': 'профессионалов класса AAA', 'Ind. Battle Masters': 'мастеров одиночной битвы', 'Ind. Battle Pro Drivers': 'профи одиночной битвы', 'Ind. Battle Semi Pro Drivers': 'полупрофи одиночной битвы', 'Team Battle Masters': 'мастеров командной битвы', 'Team Battle Pro Drivers': 'профи командной битвы', 'Team Battle Semi Pro Drivers': 'полупрофи командной битвы', 'OMD Special Ace Drivers': 'особых асов OMD', 'Team ROO Special Ace Drivers': 'особых асов ROO' })[m[1]] || m[1]}`],
    [/^A License for driver who's collected all Gold Medals from (.+?) (Delivery|Time Attack) Missions\.$/, (m) => `Licença para quem conquistou todas as medalhas de ouro das missões de ${m[2] === 'Delivery' ? 'entrega' : 'Time Attack'} de ${m[1]}.`, (m) => `Лицензия гонщика, собравшего все золотые медали миссий ${m[2] === 'Delivery' ? 'доставки' : 'Time Attack'} в ${m[1]}.`],
    [/^A license that confirms your reputation among the members of (?:the )?(.+)\.$/, (m) => `Licença que confirma sua reputação entre os membros de ${m[1]}.`, (m) => `Лицензия, подтверждающая вашу репутацию среди членов ${m[1]}.`],
    [/^(.+?) Grade ([ABC]) License$/, (m) => `Licença Grau ${m[2]} de ${m[1]}`, (m) => `Лицензия ${m[1]} класса ${m[2]}`],
    [/^(Cras|Oros|Moon Palace|Koinonia) Grade ([ABC])$/, (m) => `${m[1]} Grau ${m[2]}`, (m) => `${m[1]} класс ${m[2]}`],
    [/^Koinonia ([ABC])$/, (m) => `Koinonia ${m[1]}`, (m) => `Koinonia ${m[1]}`],
    [/^(.+?) Master License Acquired\.$/, (m) => `Licença de Mestre de ${m[1]} obtida.`, (m) => `Получена лицензия мастера ${m[1]}.`],
    [/^(.+?) Master License$/, (m) => `Licença de Mestre de ${m[1]}`, (m) => `Лицензия мастера ${m[1]}`],
    [/^(Cras|Oros|Moon Palace|Koinonia) Master$/, (m) => `Mestre de ${m[1]}`, (m) => `Мастер ${m[1]}`],
    [/^(.+?) (Delivery|Time Attack) Gold Medalist License$/, (m) => `Licença de Medalhista de Ouro ${m[2] === 'Delivery' ? 'de Entregas' : 'do Time Attack'} de ${m[1]}`, (m) => `Лицензия золотого медалиста ${m[2] === 'Delivery' ? 'доставки' : 'Time Attack'} ${m[1]}`],
    [/^Ladder ([ABC]) Grade License Acquired\.$/, (m) => `Licença Ladder Grau ${m[1]} obtida.`, (m) => `Получена лицензия Ladder класса ${m[1]}.`],
  ];
  const line = (l, lang) => {
    const s = l.trim();
    if (!s) return l;
    if (P[lang][s]) return P[lang][s];
    for (const [re, pt, ru] of TPL) { const m = s.match(re); if (m) return (lang === 'pt' ? pt : ru)(m); }
    const c = s.match(/^(.+?) (%d ?\/ ?\d+.*)$/);
    if (c && COUNT[lang][c[1]]) return `${COUNT[lang][c[1]]} ${c[2]}`;
    // two effects joined by '/': each on its own
    if (s.includes('/') && !/%d/.test(s)) return s.split('/').map((x) => line(x, lang)).join(' / ');
    return s;
  };
  window.licText = (text, lang) => {
    if (!text || (lang !== 'pt' && lang !== 'ru')) return text || '';
    return String(text).split('\n').map((l) => line(l, lang)).join('\n');
  };
  void CITY;
})();
