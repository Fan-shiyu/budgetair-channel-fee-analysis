"""The 12 golden questions and their pass criteria.

`needs`  : list of groups; the final answer must contain >=1 alternative from EACH group
           (case-insensitive substring). Number alternatives cover rounding (131,696 / 132k).
`trap`   : the answer must DECLINE (contain a decline marker) and invent no numbers.
Numbers are additionally checked by the harness's fabrication guard against tool outputs.
"""

QUESTIONS = [
    dict(id=1,
         q="What did the Aeroprice fee change cost us in 2022?",
         needs=[["131,696", "132k", "131.7k", "$132,000", "131696"],
                ["1,768", "neutral", "-$1,768", "after the change"]]),
    dict(id=2,
         q="How much do we pay on a $100 ticket now versus before?",
         needs=[["$4.00", "$4 ", "4.00"], ["$10.50", "10.50"]]),
    dict(id=3,
         q="How bad was the Aeroprice thing?",
         needs=[["131,696", "132k", "131.7k"], ["58.5%", "59%", "-58.5", "-59"]]),
    dict(id=4,
         q="Give me a quick summary I can tell my director.",
         needs=[["131,696", "132k", "131.7k"]]),
    dict(id=5,
         q="Which airlines got hit hardest and by how much?",
         needs=[["Avianca"], ["Spirit"], ["6.6", "6.64", "6.5", "6.46"]]),
    dict(id=6,
         q="Did expensive long-haul tickets win or lose?",
         needs=[["less", "win", "save", "cheaper", "pay less"], ["4.79", "$5", "-$4", "-4.79"]]),
    dict(id=7,
         q="How did LATAM one-way orders do after the change?",
         needs=[["LATAM", "LA"], ["5.32", "$5.3", "5.3", "per order"]]),
    dict(id=8,
         q="Which month was worst for cheap fares on Aeroprice?",
         # 'worst' is ambiguous; accept either data-supported extreme (lowest volume Dec, peak Jul)
         needs=[["Dec", "December", "Jul", "July"]]),
    dict(id=9,
         q="Why does a ticket under $262.50 pay more now?",
         needs=[["10.50", "$10.50 minimum", "floor"], ["4%", "4 percent", "262.50", "break-even"]]),
    dict(id=10,
         q="If we win back 500 cheap orders a month through our own site, what do we save?",
         needs=[["63,000", "$63k", "63k", "$63,000"]]),
    # --- traps ---
    dict(id=11,
         q="What will the fees look like in 2023?",
         trap=True,
         decline=["2022", "only", "cannot", "can't", "do not", "don't", "no forecast",
                  "not able", "unable", "no data", "isn't data", "is not data"]),
    dict(id=12,
         q="How much does Google Flights charge us per ticket?",
         trap=True,
         decline=["only for Aeroprice", "only known", "not in the data", "aeroprice",
                  "a5", "cannot", "can't", "don't know", "not available"]),
]
