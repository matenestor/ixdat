"""TODO @SQL update: This module contains the classes which pass on database functionality

Note on terminology:
    In ixdat, we seek to use the following naming conventions:
        `load` grabs *an object* from a database backend given its class or table name
            and the name of the specific object desired (see DataBase.load).
        `load_xxx` grabs `xxx` from a database backend given the object for which
            xxx is desired (see DataBase.load_object_data).
        `get` grabs *an object* from a database backend given its class or table name and
            the princple key (the id) of the row in the corresponding table
        `get_xxx` grabs `xxx` from a database backend given the principle key (the id) of
            the row in the table corresponding to xxx (see `Database.get`)

        So `load` works by `name` or existing object, while `get` works by `id`.
        `get_xx` is also used as the counterpart to `set_xx` to grab `xx`, typically a
        managed attribute, from an object in memory.

        `load` and `get` convention holds vertically - i.e. the Backend, the DataBase,
            up through the Saveable parent class for all ixdat classes corresponding to
            database tables have `load` and `get` methods which call downwards. TODO.
    see: https://github.com/ixdat/ixdat/pull/1#discussion_r546400793
"""
from datetime import datetime

from . import SAVEABLE_TO_DATABASE_MODEL
from .models import DBBase
from ..config import config
from ..exceptions import DataBaseError
from ..tools import thing_is_close

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class Saveable:
    table_name = None           # self-explainable
    # TODO: restructure column_attrs, extra_column_attrs, extra_linkers so that they are
    #  sufficient to fully define the tables in an SQL backend
    column_attrs = None         # common for all
    extra_column_attrs = None   # special for the object
    extra_linkers = None        # foreign keys - one2many
    # TODO: derive child_attrs somehow from the above class attributes, and have it in
    #   a way where it's easy to tell which id goes with which attribute, i.e. s_ids
    #   goes with series_list
    child_attrs = None          # foreign keys - many2many

    def __init__(self, **kw):
        super().__init__(**kw)
        self.counter = 0

    # TODO @SQL implement proper ID assignment for the lazy system
    def get_next_available_id(self, *args, **kwargs):
        ret = self.counter
        self.counter += 1
        return ret

    def save(
        self,
        # TODO @SQL determine by Measurement name or let user provide
        directory=config.standard_data_directory,
        project_name="sqlalchemy"
    ):
        assert isinstance(self, Saveable), "Don't call .save() on Saveable itself"

        ats = self.get_main_dict()

        # "metadata" model attribute is reserved by SQLAlchemy
        ats["ixd_metadata"] = ats["metadata"]
        del ats["metadata"]

        db_path = directory / project_name
        # db_name = f"{self.name}_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.sqlite"
        db_name = f"sqla_integration.sqlite"
        db_path.mkdir(parents=True, exist_ok=True)

        # engine = create_engine(f"sqlite:///{db_path / db_name}", echo=True)
        engine = create_engine(f"sqlite:///{db_name}", echo=True)
        DBBase.metadata.create_all(engine)

        # TODO @SQL probably should be checked if it is present
        model_class = SAVEABLE_TO_DATABASE_MODEL[self.__class__.__name__]

        with Session(engine) as session:
            model = model_class(**ats)
            session.add(model)
            session.commit()

        print(f">> saved measurement {str(self).split('\n')[0]} using {model_class}")

    # TODO @SQL combination of 'id', 'short_identity' and 'full_identity'
    #   should return id value from SQLite DB
    #   Maybe could be a property? Or it is available in the DB class model?
    def identity(self):
        pass

    # TODO @SQL
    def get_main_dict(self, exclude=None):
        """Return dict: serialization only of the row of the object's main table

        Args:
            exclude (list): List of attribute names to leave out of the dict
        """
        exclude = exclude or []
        if self.column_attrs is None:
            raise DataBaseError(
                f"{self!r} can't be serialized because the class "
                f"{self.__class__.__name__} hasn't defined column_attrs"
            )

        self_as_dict = {}
        for attr in self.column_attrs:
            if attr not in exclude:
                self_as_dict[attr] = getattr(self, attr)

        # TODO @SQL add 'extra_column_attrs' and 'extra_linkers'
        if hasattr(self, "extra_column_attrs") and self.extra_column_attrs:
            for table_name, extra_columns in self.extra_column_attrs.items():
                for column in extra_columns:
                    self_as_dict[column] = getattr(self, column)

        return self_as_dict

    # TODO @SQL
    def as_dict(self):
        # - save M2M relations
        #   in Measurement: "component_measurements", "calculator_list", "series_list"
        self_as_dict = self.get_main_dict(exclude=[])
        return self_as_dict

    # TODO @SQL
    def from_dict(self):
        pass

    # TODO @SQL
    # def __eq__(self, other):
    #     pass

    # TODO @SQL returns set of strings with table column names
    #   This should be handled by SQLAlchemy and easily retrievable from model
    def get_all_column_attrs(self):
        pass

    @classmethod
    def load(cls):
        pass


# TODO @SQL adjust to the new lazy system without memory backend? and to SQLAlchemy
class PlaceHolderObject:
    """A tool for ixdat's laziness, instances sit in for Saveable objects."""

    def __init__(self, identity, cls, backend=None):
        """Initiate a PlaceHolderObject with info for loading the real obj when needed

        Args:
            identity (int or tuple): The id (principle key) of the object represented OR
                the short identity, i.e. a tuple of the id and the backend. In the later
                case, identity[1] overrides a backend if given
            cls (class): Class inheriting from Saveable and thus specifiying the table
            backend (Backend, optional): by default, placeholders objects must live in
                the active backend. This is the case if loaded with get().
        """
        if isinstance(identity, int):
            i = identity
        else:
            backend, i = identity
        self.id = i
        self.cls = cls
        if not backend:  #
            backend = DB.backend
        if not backend or backend == "none" or backend is database_backends["none"]:
            raise DataBaseError(f"Can't make a PlaceHolderObject with backend={backend}")
        self.backend = backend

    def get_object(self):
        """Return the loaded real object represented by the PlaceHolderObject"""
        return self.cls.get(self.id, backend=self.backend)

    @property
    def short_identity(self):
        """Placeholder also has a short_identity to check equivalence without loading"""
        if self.backend is DB.backend:
            return self.id
        return self.backend, self.id


def fill_object_list(object_list, obj_ids, cls=None):
    """Add PlaceHolderObjects to object_list for any unrepresented obj_ids.

    Args:
        object_list (list of objects or None): The objects already known,
            in a list. This is the list to be appended to. If None, an empty
            list will be appended to.
        obj_ids (list of ints or None): The id's of objects to ensure are in
            the list. Any id in obj_ids not already represented in object_list
            is added to the list as a PlaceHolderObject
        cls (Saveable class): the class remembered by any PlaceHolderObjects
            added to the object_list, so that eventually the right object will
            be loaded. Must be specified if object_list is empty.
    """
    cls = cls or object_list[0].__class__
    object_list = object_list or []
    try:
        provided_series_ids = [s.id for s in object_list]
        print(f"DEV this has ids! {cls} {object_list[0]}")
    except:
        return object_list

    if not obj_ids:
        return object_list
    for identity in obj_ids:
        if identity not in provided_series_ids:
            object_list.append(PlaceHolderObject(identity=identity, cls=cls))
    return object_list
