_author_ = 'cjh'

import os, json, time, hashlib
import inspect
import logging
import functools
import asyncio
from urllib import parse
from aiohttp import web
from apis import APIError
from model import User
from config import configs

# 为了向装饰器传递参数，必须使用另外一个函数（在这里为get）来创建装饰器
def get(path):
    '''
    Define decorator @get('/path')
    :param path:
    :return:
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path)
    :param path:
    :return:
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

# --- 使用inspect模块中的signature方法来获取函数的参数，实现一些复用功能--
# inspect.Parameter 的类型有5种：
# POSITIONAL_ONLY		只能是位置参数
# KEYWORD_ONLY			关键字参数且提供了key
# VAR_POSITIONAL		相当于是 *args
# VAR_KEYWORD			相当于是 **kw
# POSITIONAL_OR_KEYWORD	可以是位置参数也可以是关键字参数

def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    # 如果url处理函数需要传入关键字参数，且默认是空的话，获取这个key
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    # 如果url处理函数需要传入关键字参数，获取这个key
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(name)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    # 判断是否有关键字参数
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    # 判断是否有关键字变长参数，VAR_KEYWORD对应**kw
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    # 判断是否存在一个参数叫做request，并且该参数要在其他普通的位置参数之后
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind == inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY
                      and param.kind != inspect.Parameter.VAR_KEYWORD):
            # 如果判断为True，则表明param只能是位置参数POSITIONAL_ONLY
            raise ValueError('requet parameter must be the last named parameter in function:%s%s'%(fn.__name__, str(sig)))
    return found

# RequestHandler目的就是从URL处理函数（如handlers.index）中分析其需要接收的参数，从web.request对象中获取必要的参数，
# 调用URL处理函数，然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求
class RequestHandler(object):
    def __init__(self, app, fn):
        self.app = app
        self._func_ = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_args = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = has_named_kw_args(fn)
        self.request_kw_args = has_request_arg(fn)

        # 1.定义kw对象，用于保存参数
        # 2.判断URL处理函数是否存在参数，如果存在则根据是POST还是GET方法将request请求内容保存到kw
        # 3.如果kw为空(说明request没有请求内容)，则将match_info列表里面的资源映射表赋值给kw；如果不为空则把命名关键字参数的内容给kw
        # 4.完善_has_request_arg和_required_kw_args属性
    async def __call__(self, request):
        kw = None
        # 确保有参数
        if self._has_var_kw_args or self._has_named_kw_args or self._request_kw_args:
            # ------阶段1：POST/GET方法下正确解析request的参数，包括位置参数和关键字参数----
            #
            # POST提交请求的类型(通过content_type可以指定)可以参考我的博客：http://kaimingwan.com/post/python/postchang-jian-qing-qiu-fang-shi-qian-xi
            if request.method == 'POST':
                # 判断是否村存在Content-Type（媒体格式类型），一般Content-Type包含的值：
                # text/html;charset:utf-8;
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()# 如果请求json数据格式
                    # 是否参数是dict格式，不是的话提示JSON BODY出错
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object')
                    kw = params # 正确的话把request的参数信息给kw
                # POST提交请求的类型
                elif ct.startswith('application/x-www-form-urlencode') or ct.startswith('multipart/form-data'):
                    params = await request.post() # 调用post方法，注意此处已经使用了装饰器
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-type :%s'%request.content_type)
            # get方法比较简单，直接后面跟了string来请求服务器上的资源
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    # 解析url中?后面的键值对内容保存到request_content

                    '''

                    qs = 'first=f,s&second=s'

                    parse.parse_qs(qs, True).items()

                    >>> dict([('first', ['f,s']), ('second', ['s'])])

                    '''
                    for k, v in parse.parse_qs(qs, True).item():
                        kw[k] = v[0]
        if kw is None:
            # 参数为空说明没有从request对象中获取到参数,或者URL处理函数没有参数
            '''
            def hello(request):
                    text = '<h1>hello, %s!</h1>' % request.match_info['name']
                    return web.Response()
            app.router.add_route('GET', '/hello/{name}', hello)
            '''

            '''if not self._has_var_kw_arg and not self._has_kw_arg and not self._required_kw_args:
                # 当URL处理函数没有参数时，将request.match_info设为空，防止调用出错
                request_content = dict()
            '''
            kw = dict(**request.match_info)
            # 此时kw指向match_info属性，一个变量标识符的名字的dict列表。Request中获取的命名关键字参数必须要在这个dict当中
            # kw不为空时，还要判断下是可变参数还是命名关键字参数，如果是命名关键字参数，则需要remove all unamed kw，这是为啥？

        else:
            # 如果从Request对象中获取到参数了
            # 当没有可变参数，有命名关键字参数时候，kw指向命名关键字参数的内容
            if not self._has_var_kw_args and self._named_kw_args:
                # remove all unamed kw， 从request_content中删除URL处理函数中所有不需要的参数
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg: 检查关键字参数的名字是否和match_info中的重复
            for k, v in request.match_info.item():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args:%s'%k)
                    kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw: 检查是否有必须关键字参数
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing arguement:%s'%name)
                # 以上代码均是为了获取调用参数
                logging.info('call with args :%s'%str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error = e.error, data = e.data, message = e.message)

# 添加CSS等静态文件所在路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)# app是aiohttp库里面的对象，通过router.add_router方法可以指定处理函数。本节代码自己实现了add_router。关于更多请查看aiohttp的库文档：http://aiohttp.readthedocs.org/en/stable/web.html
    logging.info('add static %s => %s'%('/static/', path))

def add_route(app, fn):
    # add_route函数，用来注册一个URL处理函数

    # 获取'__method__'和'__route__'属性，如果有空则抛出异常
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.'%str(fn))
    # 判断fn是不是协程(即@asyncio.coroutine修饰的) 并且 判断是不是fn 是不是一个生成器(generator function)
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        # 都不是的话，强行修饰为协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)'%(method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))

    # 正式注册为对应的url处理函数
    # RequestHandler类的实例是一个可以call的函数
    # 自省函数 '__call__'
    app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name):
    # 自动搜索传入的module_name的module的处理函数
    # 检查传入的module_name是否有'.'
    # Python rfind() 返回字符串最后一次出现的位置，如果没有匹配项则返回-1
    n = module_name.rfind('.')
    logging.info('n = %s' % n)
    # 没有'.',则传入的是module名

    # __import__方法使用说明请看：http://kaimingwan.com/post/python/python-de-nei-zhi-han-shu-__import__
    if n == (-1):

        # __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数,
        # 其实import语句就是调用这个函数进行导入工作的, 其返回值是对应导入模块的引用
        # __import__('os',globals(),locals(),['path','pip']) ,等价于from os import path, pip
        mod = __import__(module_name, globals(), locals())
    else:
        # name = module_name[n+1:]
        # mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
        # 上面两行是廖大大的源代码，但是把传入参数module_name的值改为'handlers.py'的话走这里是报错的，所以改成了下面这样
        mod = __import__(module_name[:n], globals(), locals())
    for attr in dir(mod):
        # 如果是以'_'开头的，一律pass，我们定义的处理方法不是以'_'开头的
        if attr.startswith('_'):
            continue
        # 获取到非'_'开头的属性或方法
        fn = getattr(mod, attr)
        # 取能调用的，说明是方法
        if callable(fn):
            # 检测'__method__'和'__route__'属性
            method =getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                # 如果都有，说明使我们定义的处理方法，加到app对象里处理route中
                add_route(app, fn)


async def logger_factory(app, handler):
    async def logger_middleware(request):
        logging.info('Request: %s %s ' % (request.method, request.path))
        return await handler(request)
    return logger_middleware()

async def response_factory(app, handler):
    async def response_middleware(request):
        r = await handler(request)
        logging.info('Request handling...')
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r ,str):
            if r.startswith('redirect'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;chatset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o:o.__dict__).encode('utf-8'))
                return resp
            else:
                resp = web.Response(body=app['__template__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r<600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))

            resp = web.Response(body=str(r).encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
    return response_middleware

async def auth_factory(app, handler):
    async def auth_middleware(request):
        if not request.path.startswith('/static'):
            logging.info('check user: %s %s '%(request.method, request.path))
            request.__user__ = None
            cookie_str = request.cookies.get(configs.cookie.name)
            if cookie_str:
                user = await cookie2user(cookie_str)
                if user:
                    logging.info('set current user:%s'%user.email)
                    request.__user__ = user
            if request.path.startswith('/manage') and (request.__user__ is None or (not configs.show_manage_page and not request.__user__.admin)):
                return web.HTTPFound('/login')
        return await handler(request)
    return auth_middleware()

def user2cookie(user, max_age):
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s'%(user.id, user.passwd, expires, configs.cookie.key)
    L =[user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s'%(uid, user.password, expires, configs.cookie.key)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.password = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

# 用于分页
class Page(object):
    """docstring for Page"""

    # 参数说明：

    # item_count：要显示的条目数量

    # page_index：要显示的是第几页

    # page_size：每页的条目数量，为了方便测试现在显示为2条
    def __init__(self, item_count, page_index = 1, page_size = 10, page_show = 3):
        self.item_count = item_count
        self.page_size = page_size
        # 计算出应该有多少页才能显示全部的条目
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        self.page_show = page_show - 2 # 去掉始终显示的首页和末页的两项
        # 如果没有条目或者要显示的页超出了能显示的页的范围
        if(item_count == 0) or (page_index > self.page_count):
            # 则不显示
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            # 否则说明要显示

            # 设置显示页就是传入的要求显示的页
            self.page_index = page_index
            # 这页的初始条目的offset
            self.offset = self.page_size * (page_index - 1)
            # 这页能显示的数量
            self.limit = self.page_size
        # 这页后面是否还有下一页
        self.has_next = self.page_index < self.page_count
        # 这页之前是否还有上一页
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count:%s, page_count:%s, page_index:%s, page_size:%s, offset:%s, limit:%s'%(self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__


    @classmethod
    def page2int(cls, str):
        p = 1
        try:
             p = int(str)
        except ValueError:
            pass
        if p < 1:
            p = 1
        return p

    def pagelist(self):
        left = 2
        right = self.page_count
        if (self.page_count > self.page_show):
            left = self.page_index - (self.page_show // 2)
            if (left < 2):
                left = 2
            right = left + self.page_show
            if (right > self.page_count):
                right = self.page_count
                left = right - self.page_show
        self.pagelist = list(range(left, right))

def filelist(dir):
    filelist = []
    l = os.listdir(dir)
    for file in l:
        if os.path.isfile(os.path.join(dict, file)) and not file.startswith('.'):
            filelist.append(file)
    return filelist