"""Create the terminal demo GIF from the verified run on 21 October 2026."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SCENES = [
"""PS> uv run valutatrade
ValutaTrade Hub — виртуальный валютный кошелёк
valutatrade> update-rates
Обновлено курсов: 6
Последнее обновление: 2026-10-21T12:32:17+00:00""",
"""valutatrade> show-rates
+--------+----------------+------------------+
| Валюта |   Курс в USD   |     Источник     |
+--------+----------------+------------------+
|  BTC   | 83500.00000000 |    CoinGecko     |
|  ETH   | 2466.90000000  |    CoinGecko     |
|  EUR   |   1.12271247   | ExchangeRate-API |
|  GBP   |   1.33636242   | ExchangeRate-API |
|  RUB   |   0.01211123   | ExchangeRate-API |
|  SOL   |  106.89000000  |    CoinGecko     |
+--------+----------------+------------------+
Обновлено: 2026-10-21T12:32:17+00:00 (UTC)""",
"""valutatrade> get-rate --from BTC --to USD
Курс BTC→USD: 83500.00000000
Обновлено: 2026-10-21T12:32:17+00:00
Источник: CoinGecko
Обратный курс USD→BTC: 0.00001198""",
"""valutatrade> get-rate --from EUR --to USD
Курс EUR→USD: 1.12271247
Источник: ExchangeRate-API
Обратный курс USD→EUR: 0.89070000

valutatrade> get-rate --from USD --to RUB
Курс USD→RUB: 82.56800000
Источник: ExchangeRate-API
Обратный курс RUB→USD: 0.01211123""",
"""valutatrade> register --username finaldemo2026 --password 1234
Пользователь 'finaldemo2026' зарегистрирован (id=2).

valutatrade> login --username finaldemo2026 --password 1234
Вы вошли как 'finaldemo2026'""",
"""valutatrade> deposit-demo --amount 10000
Добавлено 10000.00 виртуальных USD.
Баланс: 10000.00 USD

valutatrade> show-portfolio
Портфель пользователя 'finaldemo2026' (база: USD):
  USD: 10000.0000 → 10,000.00 USD
ИТОГО: 10,000.00 USD""",
"""valutatrade> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC
Курс: 83500.00000000 USD/BTC
  BTC: было 0.0000 → стало 0.0500
  USD: было 10000.0000 → стало 5825.0000
Стоимость покупки: 4,175.00 USD""",
"""valutatrade> show-portfolio
Портфель пользователя 'finaldemo2026' (база: USD):
  BTC: 0.0500 → 4,175.00 USD
  USD: 5825.0000 → 5,825.00 USD
ИТОГО: 10,000.00 USD""",
"""valutatrade> sell --currency BTC --amount 0.01
Продажа выполнена: 0.0100 BTC
Курс: 83500.00000000 USD/BTC
  BTC: было 0.0500 → стало 0.0400
  USD: было 5825.0000 → стало 6660.0000
Выручка: 835.00 USD""",
"""valutatrade> show-portfolio --base EUR
Портфель пользователя 'finaldemo2026' (база: EUR):
  BTC: 0.0400 → 2,974.94 EUR
  USD: 6660.0000 → 5,932.06 EUR
ИТОГО: 8,907.00 EUR""",
"""valutatrade> history
2026-10-21T12:34:22+00:00 DEMO_DEPOSIT 10000.0000 USD
2026-10-21T12:34:28+00:00 BUY 0.0500 BTC
2026-10-21T12:34:35+00:00 SELL 0.0100 BTC""",
"""valutatrade> sell --currency BTC --amount 100
Ошибка: Недостаточно средств
Доступно 0.0400 BTC, требуется 100.0000 BTC

valutatrade> buy --currency BTC --amount -1
Ошибка: 'amount' должен быть положительным числом""",
"""valutatrade> get-rate --from ABC --to USD
Ошибка: Неизвестная валюта 'ABC'
Поддерживаются: USD, EUR, GBP, RUB, BTC, ETH, SOL.

valutatrade> register --username finaldemo2026 --password 1234
Ошибка: Имя пользователя 'finaldemo2026' уже занято""",
"""valutatrade> exit
До свидания!

PS> uv run valutatrade
ValutaTrade Hub — виртуальный валютный кошелёк
valutatrade> login --username finaldemo2026 --password 1234
Вы вошли как 'finaldemo2026'""",
"""valutatrade> show-portfolio
Портфель пользователя 'finaldemo2026' (база: USD):
  BTC: 0.0400 → 3,340.00 USD
  USD: 6660.0000 → 6,660.00 USD
ИТОГО: 10,000.00 USD

valutatrade> history
2026-10-21T12:34:22+00:00 DEMO_DEPOSIT 10000.0000 USD
2026-10-21T12:34:28+00:00 BUY 0.0500 BTC
2026-10-21T12:34:35+00:00 SELL 0.0100 BTC""",
]
W,H=1080,620
COLORS=[(13,17,23),(20,25,33),(35,41,52),(225,232,240),
        (117,209,181),(156,169,184),(255,184,108),(250,132,128),
        (93,115,140),(222,117,117),(237,191,103),(113,190,151)]
font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",19)
bold=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",18)
small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",14)
palette=Image.new("P",(1,1))
palette.putpalette([v for rgb in COLORS for v in rgb]+[0]*(768-len(COLORS)*3))
frames=[]
for i, scene in enumerate(SCENES,1):
    im=Image.new("RGB",(W,H),COLORS[0])
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((18,18,W-18,H-18),radius=13,fill=COLORS[1],outline=COLORS[8],width=1)
    d.rounded_rectangle((18,18,W-18,70),radius=13,fill=COLORS[2])
    d.rectangle((18,52,W-18,70),fill=COLORS[2])
    for n,col in enumerate((9,10,11)):
        x=39+n*22
        d.ellipse((x,38,x+11,49),fill=COLORS[col])
    d.text((122,34),"ValutaTrade Hub  —  проверка CLI",font=bold,fill=COLORS[3])
    d.text((W-116,35),f"{i:02d}/{len(SCENES):02d}",font=small,fill=COLORS[5])
    y=100
    for ln in scene.splitlines():
        color=COLORS[3]
        if ln.startswith(("valutatrade>","PS>")): color=COLORS[4]
        elif ln.startswith("Ошибка:"): color=COLORS[7]
        elif ln.startswith(("ИТОГО:","Обновлено курсов:")): color=COLORS[6]
        elif ln.startswith(("Источник:","Обновлено:","Последнее обновление:")): color=COLORS[5]
        d.text((48,y),ln,font=font,fill=color)
        assert d.textbbox((48,y),ln,font=font)[2] < W-24, (i,ln)
        y+=33
    assert y < H-45, (i,y)
    d.line((43,H-65,W-43,H-65),fill=COLORS[8])
    d.text((48,H-52),"М26-555  ·  Консольный симулятор",font=small,fill=COLORS[5])
    d.text((W-215,H-52),"Данные: 21.10.2026",font=small,fill=COLORS[5])
    frames.append(im.quantize(palette=palette,dither=Image.Dither.NONE))
output=Path("docs/valutatrade_demo.gif")
frames[0].save(output,save_all=True,append_images=frames[1:],
               duration=[1700,2900]+[1800]*12+[3000],
               loop=0,optimize=False,disposal=2,transparency=None)
print("Wrote",output,output.stat().st_size,"bytes")
