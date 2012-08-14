# Copyright European Organization for Nuclear Research (CERN)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Authors:
# - Angelos Molfetas, <angelos.molfetas@cern.ch>, 2012
# - Mario Lassnig, <mario.lassnig@cern.ch>, 2012
# - Vincent Garonne,  <vincent.garonne@cern.ch> , 2011

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import DisconnectionError

from rucio.common.config import config_get
from rucio.db import models1 as models


def _fk_pragma_on_connect(dbapi_con, con_record):
        # Hack for previous versions of sqlite3
        try:
            dbapi_con.execute('pragma foreign_keys=ON')
        except AttributeError:
            pass


def ping_listener(dbapi_conn, connection_rec, connection_proxy):

    """
    Ensures that MySQL connections checked out of the
    pool are alive.

    Borrowed from:
    http://groups.google.com/group/sqlalchemy/msg/a4ce563d802c929f

    :param dbapi_conn: DBAPI connection
    :param connection_rec: connection record
    :param connection_proxy: connection proxy
    """

    try:
        dbapi_conn.cursor().execute('select 1')
    except dbapi_conn.OperationalError, ex:
        if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
            msg = 'Got mysql server has gone away: %s' % ex
            raise DisconnectionError(msg)
        else:
            raise


def get_session():
    """ Creates a session to a specific database, assumes that schema already in place.
        :returns: session """

    database = config_get('database', 'default')
    engine = create_engine(database, echo=False, echo_pool=False)
    if 'mysql' in database:
        event.listen(engine, 'checkout', ping_listener)

    event.listen(engine, 'connect', _fk_pragma_on_connect)
    return scoped_session(sessionmaker(bind=engine, autocommit=False, autoflush=True, expire_on_commit=True))


def build_database(echo=True):
    """ Applies the schema to the database. Run this command once to build the database. """

    engine = create_engine(config_get('database', 'default'), echo=echo)
    models.register_models(engine)


def destroy_database(echo=True):
    """ Removes the schema from the database. Only useful for test cases or malicious intents. """

    engine = create_engine(config_get('database', 'default'), echo=echo)
    models.unregister_models(engine)


def create_root_account():
    """ Inserts the default root account to an existing database. Make sure to change the default password later. """

    session = get_session()

    # Account=root
    account = models.Account(account='root', type='user', status='active')
    # Username/Password authentication
    # username=ddmlab
    # password=secret
    identity1 = models.Identity(identity='ddmlab', type='userpass', password='2ccee6f6dd1bc2269cddd7cd5e47578e98e430539807c36df23fab7dd13e7583', salt='0', email='ph-adp-ddm-lab@cern.ch')
    iaa1 = models.IdentityAccountAssociation(identity=identity1.identity, type=identity1.type, account=account.account, default=True)

    # X509 authentication
    # Default DDMLAB client certificate from /opt/rucio/etc/web/client.crt
    identity2 = models.Identity(identity='/C=CH/ST=Geneva/O=CERN/OU=PH-ADP-CO/CN=DDMLAB Client Certificate/emailAddress=ph-adp-ddm-lab@cern.ch', type='x509', email='ph-adp-ddm-lab@cern.ch')
    iaa2 = models.IdentityAccountAssociation(identity=identity2.identity, type=identity2.type, account=account.account, default=True)

    # GSS authentication
    identity3 = models.Identity(identity='ddmlab@CERN.CH', type='gss', email='ph-adp-ddm-lab@cern.ch')
    iaa3 = models.IdentityAccountAssociation(identity=identity3.identity, type=identity3.type, account=account.account, default=True)

    # Apply
    session.add_all([account, identity1, identity2, identity3])
    session.commit()
    session.add_all([iaa1, iaa2, iaa3])
    session.commit()
