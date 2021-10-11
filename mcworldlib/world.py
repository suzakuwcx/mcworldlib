# This file is part of MCWorldLib
# Copyright (C) 2019 Rodrigo Silva (MestreLion) <linux@rodrigosilva.com>
# License: GPLv3 or later, at your choice. See <http://www.gnu.org/licenses/gpl>

"""Minecraft World save directory. The top level hierarchy.

Exported items:
    load  -- Helper function to load a world. Alias to World.load()
    World -- Class representing a Minecraft World save directory and associated data.
"""

__all__ = ['load', 'World']


import logging
import os.path

import tqdm

from . import anvil
from . import level
from . import nbt
from . import util as u

log = logging.getLogger(__name__)


class WorldNotFoundError(u.MCError, IOError): pass


class World(level.Level):
    """Save directory and all related files and objects"""

    __slots__ = (
        'path',
        'dimensions',
    )

    # A.K.A Dimension subdirs
    _categories = (
        'region',
        'entities',
        'poi'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = ""
        self.dimensions = {}

    @property
    def name(self):
        return str(self.root.get('LevelName', os.path.basename(self.path)))

    @name.setter
    def name(self, value):
        self.root['LevelName'] = nbt.String(value)

    @property
    def level(self):
        """Somewhat redundant API shortcut, as for now World *is* a Level"""
        return self.root

    def _category_dict(self, category):
        return {k: v.get(category, {}) for k, v in self.dimensions.items()}

    @property
    def regions(self):
        """Re-shaped dimensions dictionary containing only Region data"""
        return self._category_dict('region')

    @property
    def entities(self):
        """Re-shaped dimensions dictionary containing only Entities data"""
        return self._category_dict('region')

    @property
    def poi(self):
        """Re-shaped dimensions dictionary containing only Point-of-Interest data"""
        return self._category_dict('poi')

    @property
    def chunk_count(self):
        return sum(len(_) for _ in self.regions)

    def get_chunks(self, progress=True, dimension=u.Dimension.OVERWORLD):
        """Yield all chunks in a given dimension, Overworld by default"""
        regions = self.dimensions[dimension].values()
        if progress:
            regions = tqdm.tqdm(regions)
        for region in regions:
            for chunk in region.values():
                yield chunk

    def get_all_chunks(self, progress=True):
        """Yield a (dimension, chunk) tuple for all chunks in all dimensions"""
        dimensions = self.dimensions.keys()
        if progress:
            dimensions = tqdm.tqdm(dimensions)
        for dimension in dimensions:
            for chunk in self.get_chunks(progress=progress, dimension=dimension):
                yield dimension, chunk

    def get_chunk_at(self, pos, dimension=u.Dimension.OVERWORLD):
        if not isinstance(pos, u.Pos):
            pos = u.Pos(*pos)
        return self.dimensions[dimension][pos.as_region][pos.as_region_chunk]

    def get_block_at(self, pos, dimension=u.Dimension.OVERWORLD):
        if not isinstance(pos, u.Pos):
            pos = u.Pos(*pos)
        chunk = self.get_chunk_at(pos, dimension)
        palette, indexes = chunk.get_section_blocks(pos.as_section)
        if not palette:
            return None
        return palette[int(indexes[pos.as_section_block])]

    def get_player(self, name=None):
        """Get a named player (server) or the world default player"""
        # Single Player
        if name is None or name == 'Player':
            try:
                return self.player
            except Exception:
                raise u.MCError("Player not found in world '%s': %s" %
                                (self.name, name))
        # Multiplayer
        raise NotImplementedError

    @classmethod
    def load(cls, path, progress=True, **kwargs):
        self: 'World'

        # /level.dat and directory path
        if hasattr(path, 'name'):
            # Assume file-like buffer to level.dat
            self = cls.parse(path)
            self.path = os.path.dirname(path.name)
        elif os.path.isfile(path):
            # Assume level.dat itself
            self = super().load(path, **kwargs)
            self.path = os.path.dirname(path)
        elif os.path.isdir(path):
            # Assume directory containing level.dat
            self = super().load(os.path.join(path, 'level.dat'), **kwargs)
            self.path = path
        else:
            # Last chance: try path as name of a minecraft save dir
            path = os.path.expanduser(os.path.join(u.MINECRAFT_SAVES_DIR, path))
            if os.path.isdir(path):
                self = super().load(os.path.join(path, 'level.dat'), **kwargs)
                self.path = path
            else:
                # self = cls()  # blank world
                raise WorldNotFoundError(f"World not found: {path}")

        log.info("Loading World '%s': %s", self.name, self.path)

        # Dimensions and their Region files and associated data
        # /region, /DIM-1/region, /DIM1/region
        # TODO: Read custom dimensions! /dimensions/<prefix>/<name>/region
        for dimension in u.Dimension:
            self.dimensions[dimension] = {}
            for category in self._categories:
                self.dimensions[dimension][category] = anvil.Regions.load(self, dimension, category)

        # ...

        return self


load = World.load
