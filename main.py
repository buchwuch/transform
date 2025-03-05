import pandas as pd
import re
from pathlib import Path
from decimal import Decimal, getcontext
from gooey import Gooey, GooeyParser

import logging
log = logging.getLogger(__name__)

# Set the precision to 50 decimal places, definitely overkill but doesn't hurt to be precise
getcontext().prec = 50

# Define the value of pi
PI = Decimal('3.14159265358979323846264338327950288419716939937510')
VAR = Decimal("0.2375")

def calc_rec(row) -> Decimal:
    term_1 = Decimal(2) * PI * row["freq/Hz"]
    term_2 = row["Re(Z)/Ohm"]**2 + row["-Im(Z)/Ohm"]**2
    term_3 = PI * (VAR**2)
    return row["-Im(Z)/Ohm"] / (term_1 * term_2 * term_3) * Decimal(1_000_000)

def calc_imc(row) -> Decimal:
    term_1 = Decimal(2) * PI * row["freq/Hz"]
    term_2 = row["Re(Z)/Ohm"]**2 + row["-Im(Z)/Ohm"]**2
    term_3 = PI * (VAR**2)
    return row["Re(Z)/Ohm"] / (term_1 * term_2 * term_3) * Decimal(1_000_000)


def read_file(file: Path):
    with open(file, "r", encoding="ISO-8859-1") as fh:
        while True:
            position = fh.tell()
            line = fh.readline()
            if line == "":
                raise ValueError("unexpected file format")
            if line.startswith("freq/Hz"):
                fh.seek(position)
                break
        return pd.read_csv(fh, encoding="ISO-8859-1", delimiter="\t", dtype=str)

def load_file(file: Path):
    try:
        df = read_file(file)
        return process_table(df)
    except Exception as e:
        log.error(f"Failed to load {file=} : {e}")
        raise

def process_table(df):
    # map everything to decimal
    for col in df.columns:
        df[col] = df[col].apply(Decimal)

    if "-Im(Z)/Ohm" not in df.columns:
        assert "Im(Z)/Ohm" in df.columns, f"missing Im(Z)/ohm column"
        df["-Im(Z)/Ohm"] = df["Im(Z)/Ohm"] * Decimal(-1)

    df["ReC"] = df.apply(calc_rec, axis=1)
    df["ImC"] = df.apply(calc_imc, axis=1)
    return df[["freq/Hz", "Re(Z)/Ohm", "-Im(Z)/Ohm", "ReC", "ImC"]]


def process_files(source: Path, output: Path):
    result = pd.DataFrame()
    pattern = r"(.+)_(\d+)_(.+)_C(\d+)\.txt$"
    processed = []
    for i, entry in enumerate(sorted(source.iterdir())):
        match = re.search(pattern, entry.name)
        if not match:
            log.info(f"Skipping entry={entry}")
            continue
        number = match.group(2)
        entry_df = load_file(entry)
        if i == 0:
            result["freq/Hz"] = entry_df["freq/Hz"]
        for column in entry_df.columns[1:]:
            new_column = column
            if column == "-Im(Z)/Ohm":
                new_column = f'"{column}_{number}"'
            else:
                new_column = f"{column}_{number}"

            result[new_column]  = entry_df[column]
        processed.append(entry)
    result.to_csv(output, index=False)

    files = "\n".join("\t" + file.name for file in processed)
    log.info(f"Processed {len(processed)} file(s) \n{files}")

@Gooey
def main():
    from argparse import ArgumentParser
    p = GooeyParser(description="col col aggregator")
    p.add_argument("source", widget="FileChooser")
    p.add_argument("output", widget="FileChooser")
    # p = ArgumentParser()
    # p.add_argument("--source", type=Path, required=True)
    # p.add_argument("--output", type=Path, required=True)
    logging.basicConfig(level=logging.DEBUG)
    args = p.parse_args()
    source: Path = Path(args.source).expanduser().resolve()
    output: Path = Path(args.output)

    if not source.exists():
        log.info(f"{source=} does not exist")

    if not source.is_dir():
        source = source.parent
    if output.is_dir():
        output = output.joinpath("ColColOutput.csv")

    process_files(source, output)

if __name__ == "__main__":
    main()
