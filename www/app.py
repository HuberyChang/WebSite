import logging
logging.basicConfig(level=logging.INFO)
import asyncio, json, os, time, orm
from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from config_default import configs
from webframe import add_routes, add_static, logger_factory, response_factory, auth_factory


def init_jinja2(app, **kwargs):
    logging.info('init jinja2...')
    options = dir(
        autoescape = kwargs.get('autoescape', True),
        auto_reload = kwargs.get('auto_reload', True)
    )
    path = kwargs.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s'%path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kwargs.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__template_env__'] = env


def deltatime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟以前'
    if delta < 3600:
        return u'%s分钟前'%(delta // 60)
    if delta < 84600:
        return u'%s小时前'%(delta // 3600)
    if delta < 604800:
        return u'%s天前'%(delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%日'%(dt.year, dt.month, dt.day)

def date_filter(t):
    dt = datetime.fromtimestamp(t)
    return u'%s-%s-%s'%(dt.year, dt.month, dt.day)

async def on_close(app):
    await orm.close_pool()

async def init(loop):
    rs = dict()
    await orm.create_pool(loop, **configs.database)
    app = web.Application(loop=loop, middlewares=[logger_factory, logger_factory, auth_factory])
    app.on_shutdown.append(on_close)
    init_jinja2(app, filters=dict(deltatime=deltatime_filter, date=date_filter))
    add_routes(app, 'handlers')
    add_static(app)
    handler = app.make_handler()
    srv = await loop.create_server(handler, '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    rs['app'] = app
    rs['srv'] = srv
    rs['handler'] = handler
    return rs
loop = asyncio.get_event_loop()
rs = loop.run_until_complete(init(loop))
try:
    loop.run_forever()
except KeyboardInterrupt:
    logging.info('Exit server by manual')
finally:
    rs['srv'].close()
    loop.run_until_complete(rs['srv'].wait_closed())
    loop.run_until_complete(rs['app'].shutdown())
    loop.run_until_complete(rs['handler'].finish_connections(60.0))
    loop.run_until_complete(rs['app'].cleanup())
loop.close()