# Retail chains per market (reference)

The dashboard separates **market** (country, which also fixes the currency) from
**retail chain** (Handelskette). A chain such as a discounter can operate in
Germany, Austria and Switzerland; the same banner is then compared across countries
on the *Marktkarte* tab. A chain that exists in one country only (a regional
supermarket) simply has one cell.

## What the demo data contains
Three **fictional** chains, so that no real company is shown with invented numbers:

| Demo chain | Mimics | Countries | Stores |
|---|---|---|---|
| MarktHaus | national supermarket | DE | Munich, Ingolstadt |
| PreisPunkt | discounter active in all of DACH | DE, AT, CH | Berlin, Vienna, Zurich |
| AlpenFrisch | Alpine regional chain | AT, CH | Graz, Pfaeffikon SZ |

All sales, stock and costs are synthetic (see `synthetic-data.md`).

## Real chains, as general orientation
Not used in the demo data. Check the current list before using it in a customer setting;
store networks, brands and group structures change.

| Market | Examples |
|---|---|
| Germany | REWE Group, Edeka, Aldi Nord, Aldi Sued, Lidl, Kaufland, Netto, Penny |
| Austria | Spar, REWE International (Billa, Penny), Hofer (the Aldi Sued banner in Austria), Lidl, MPreis |
| Switzerland | Migros, Coop, Aldi Suisse, Lidl, Denner, Volg |

Aldi and Lidl are the usual examples of a chain present in all three countries.
Note that Hofer in Austria and Aldi Suisse in Switzerland are the local names of the
Aldi group, so a real data set may use a different banner per country. Map those to one
chain value before upload if you want a cross-country comparison.

## How to use your own chains
Add a `chain` column (aliases: `Handelskette`, `Kette`, `retailer`, `banner`) to the sales
file. The store id keeps the country prefix (`DE-`, `AT-`, `CH-`), which decides market and
currency. Without a chain column everything works as before; the chain switch and the
map are then hidden or empty.
