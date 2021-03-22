from collections import ChainMap
from functools import lru_cache
from typing import List

import click
import pycountry
from sdmx.model import Annotation, Code

from message_ix_models.util import as_codes, load_package_data


@lru_cache()
def get_codes(name: str) -> List[Code]:
    """Return codes for the set `name` in MESSAGE-GLOBIOM scenarios.

    The information is read from :file:`data/{name}.yaml`, e.g.
    :file:`data/technology.yaml`.

    When `name` includes "node", then child codes are automatically populated from the
    ISO 3166 database via :mod:`pycountry`. For instance:

    .. code-block:: yaml

       myregion:
         name: Custom region
         child: [AUT, SCG]

    …results in a region with child codes for Austria (a current country) and the
    formerly-existing country Serbia and Montenegro.

    Parameters
    ----------
    name : :class:`str`
        Any :file:`.yaml` file in the folder :file:`message_ix_models/data/`.

    Returns
    -------
    list of :class:`~sdmx.model.Code`
        Every Code has :attr:`id`, :attr:`name`, :attr:`description`, and
        :attr:`annotations` attributes. Calling :func:`str` on a code returns its
        :attr:`id`.
    """
    # Raw contents of the config file
    config = load_package_data(name)

    if "node" in name:
        # Automatically add information for countries within regions in the node
        # codelists. Use a ChainMap to combine a the `config` loaded from file and then
        # fall back to contents of the pycountry databases.
        config = ChainMap(
            config,
            # Create codes using the ISO database via pycountry
            {c.alpha_3: dict(id=c.alpha_3, name=c.name) for c in pycountry.countries},
            # Also include historic countries
            {
                c.alpha_3: dict(id=c.alpha_3, name=c.name)
                for c in pycountry.historic_countries
            },
        )

    # Convert to codes
    data = as_codes(config)

    # Fill in additional data, defaults, etc.
    if name == "technology":
        process_technology_codes(data)
    elif name == "year":
        process_year_codes(data)

    return data


def process_technology_codes(codes):
    """Process a list of codes for ``technology``.

    This function ensures every code has an annotation with id "vintaged", default
    :obj:`False`.
    """
    for code in codes:
        try:
            anno = code.pop_annotation(id="vintaged")
        except KeyError:
            # Default value for 'vintaged'
            anno = Annotation(id="vintaged", text=repr(False))

        code.annotations.append(anno)


def process_year_codes(codes):
    """Process a list of codes for ``year`` (time periods)."""
    pass


@click.command(name="techs")
@click.pass_obj
def cli(ctx):
    """Export metadata to technology.csv.

    This command transforms the technology metadata from the YAML file to CSV format.
    """
    import pandas as pd

    # Convert each code to a pd.Series
    data = []
    for code in get_codes("technology"):
        # Base attributes
        d = dict(id=code.id, name=str(code.name), description=str(code.description))

        # Annotations
        for anno in ("type", "vintaged", "sector", "input", "output"):
            try:
                d[anno] = str(code.get_annotation(id=anno).text)
            except KeyError:
                pass

        data.append(pd.Series(d))

    # Combine series to a data frame
    techs = pd.DataFrame(data)

    # Write to file
    dest = ctx.get_local_path("technology.csv")
    print(f"Write to {dest}")

    techs.to_csv(dest, index=None, header=True)

    # Print the first few items of the data frame
    print(techs.head())
