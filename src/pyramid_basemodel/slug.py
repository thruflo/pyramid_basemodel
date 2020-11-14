# -*- coding: utf-8 -*-

"""Provides a base ORM mixin for models that need a name and a url slug."""

__all__ = [
    'BaseSlugNameMixin',
]

import logging
logger = logging.getLogger(__name__)

import slugify

from sqlalchemy import exc as sa_exc
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext import declarative 
from sqlalchemy.schema import Column
from sqlalchemy.types import Unicode

from pyramid_basemodel.util import ensure_unique
from pyramid_basemodel.util import generate_random_digest

from pyramid_basemodel import Session

class BaseSlugNameMixin(object):
    """ORM mixin class that provides ``slug`` and ``name`` properties, with a
      ``set_slug`` method to set the slug value from the name and a default
      name aware factory classmethod.
    """
    
    _max_slug_length = 64
    _slug_is_unique = True

    @property
    def __name__(self):
        return self.slug
    
    
    @declarative.declared_attr
    def slug(cls):
        """A url friendly slug, e.g.: `foo-bar`."""
        
        l = cls._max_slug_length
        is_unique = cls._slug_is_unique
        return Column(Unicode(l), nullable=False, unique=is_unique)

    @declarative.declared_attr
    def name(cls):
        """A human readable name, e.g.: `Foo Bar`."""
        
        l = cls._max_slug_length
        return Column(Unicode(l), nullable=False)

    def set_slug(self, candidate=None, **kwargs):
        """
        Generate and set a unique ``self.slug`` from ``self.name``.

        :param get_digest: function to generate random digest. Used of there's no name set.
        :param inspect:
        :param session: SQLAlchemy's session
        :param to_slug: slugify function
        :param unique: unique function
        """
        
        # Compose.
        gen_digest = kwargs.get('gen_digest', generate_random_digest)
        inspect = kwargs.get('inspect', sa_inspect)
        session = kwargs.get('session', Session)
        to_slug = kwargs.get('to_slug', slugify.slugify)
        unique = kwargs.get('unique', ensure_unique)

        # Generate a candidate slug.
        if candidate is None:
            if self.name:
                candidate = to_slug(self.name)
            if not candidate:
                candidate = gen_digest(num_bytes=16)
        
        # Make sure it's not longer than 64 chars.
        l = self._max_slug_length 
        l_minus_ellipsis = l - 3
        candidate = candidate[:l]
        unique_candidate = candidate[:l_minus_ellipsis]

        # If there's no name, only set the slug if its not already set.
        if self.slug and not self.name:
            return
        
        # If there is a name and the slug matches it, then don't try and
        # reset (i.e.: we only want to set a slug if the name has changed).
        if self.slug and self.name:
            if self.slug == candidate:
                # XXX as long as the instance is pending, as otherwise
                # we skip checking uniqueness on unsaved instances.
                try:
                    insp = inspect(self)
                except sa_exc.NoInspectionAvailable:
                    pass
                else:
                    if insp.persistent or insp.detached:
                        return

        # Iterate until the slug is unique.
        with session.no_autoflush:
            slug = unique(self, self.query, self.__class__.slug, unique_candidate)

        # Finally set the unique slug value.
        self.slug = slug
