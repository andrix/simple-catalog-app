"""Database set up module.

This module has the models and the  code to set up the database.
By default we use `sqlite`.

To create an empty database run:

   $ python database_setup.py

This command will create a `categories.db` database.
"""

import json

from sqlalchemy.sql import func
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    email = Column(String(256), nullable=False)
    picture = Column(String(256), nullable=True)


class Category(Base):

    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship(User)


class Item(Base):

    __tablename__ = "item"

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    description = Column(String(2048), nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), onupdate=func.now())

    category_id = Column(Integer, ForeignKey("category.id"))
    category = relationship(
        Category,
        cascade="save-update, merge, refresh-expire, expunge",
        single_parent=True
    )

    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship(User)

    def serialize(self):
        """Serialize the object into a python dictionary.

        Returns:
            A python dictionary with the content of the Item.
        """

        item = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created": self.created.isoformat(),
            "category": self.category.name,
        }
        if self.updated:
            item["updated"] = self.updated.isoformat()
        return item

    def json(self):
        """Serialize the object and return a JSON string.

        Returns:
            str: a JSON representation of the `item`.
        """
        return json.dumps(self.serialize())


engine = create_engine("sqlite:///categories.db")
Base.metadata.create_all(engine)
