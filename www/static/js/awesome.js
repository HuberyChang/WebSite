// patch for lower-version IE:
if(! window.console){
    window.console = {
        log : function () {},
        info : function () {},
        error : function () {},
        warn : function () {},
        debug : function () {}
    };
}


// patch for string.trim():
if(! String.prototype.trim){
    String.prototype.trim = function () {
        return this.replace(/^\s+|\s+$/g, '');
    };
}



if(! Number.prototype.toDateTime){
    var replaces = {
        'yyyy' : function (dt) {
            return dt.getFullYear().toString();
        },
        'yy' : function (dt) {
            return (dt.getFullYear()%100).toString();
        },
        'MM' : function (dt) {
            var m = dt.getMonth() + 1;
            return m < 10 ? '0' + m : m.toString();
        },
        'M' : function (dt) {
            var m = dt.getMonth() + 1;
            return m.toString();
        },
        'dd' : function (dt) {
            var d = dt.getDate();
            return d < 10 ? '0' + d : d.toString();
        },
        'd' : function (dt) {
            var d = dt.getDate();
            return d.toString();
        },
        'hh' : function (dt) {
            var h = dt.getHours();
            return h < 10 ? '0' + h : h.toString();
        },
        'h' : function (dt) {
            var h = dt.getHours();
            return h.toString();
        },
        'mm' : function (dt) {
            var m = dt.getMinutes();
            return m < 10 ? '0' + m : m.toString();
        },
        'm' : function (dt) {
            var m = dt.getMinutes();
            return m.toString();
        },
        'ss' : function (dt) {
            var s = dt.getSeconds();
            return s < 10 ? '0' + s : s.toString();
        },
        's' : function (dt) {
            var s = dt.getSeconds();
            return s.toString();
        },
        'a' : function (dt) {
            var h = dt.getHours();
            return h < 12 ? 'AM' : 'PM';
        }
    };
    var token = /([a-zA-Z]+)/;
    Number.prototype.toDateTime = function (format) {
        var fmt = format || 'yyyy-MM-dd hh:mm:ss'
        var dt = new Date(this*1000);
        var arr = fmt.split(token);
        for(var i=0;i<arr.length;i++){
            var s = arr[i];
            if(s&&s in replaces){
                arr[i] = replaces[s](dt);
            }
        }
        return arr.join('');
    };
}


function encodeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quto;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}


function parseQueryString() {
    var q = location.search,
        r = {},
        i, pos, s, qs;
    if(q && q.charAt(0)==='?'){
        qs = q.substring(1).split('&');
        for (i=0; i<qs.length; i++){
            s = qs[i];
            pos = s.indexOf('=');
            if(pos <= 0){
                continue;
            }
            r[s.substring(s, pos)] = decodeURIComponent(s.substring(pos+1)).replace(/\+/g, ' ');
        }
    }
    return r;
}



function gotoPage(i) {
    var r = parseQueryString();
    r.page = i;
    location.assign('?' + $.param(r));
}



function refresh() {
    var t = new Date().getTime(),
        url = location.pathname;
    if(location.search){
        url = url + location.search + '&t=' + t;
    }
    else {
        url = url + '?t=' + t;
    }
    location.assign(url);
}


function toSmartDate(timestamp) {
    if(typeof (timestamp) === 'string'){
        timestamp = parseInt(timestamp);
    }
    if(isNaN(timestamp)){
        return '';
    }
    var today = new Date(g_time),
        now = today.getTime(),
        s = '1分钟前',
        t = now - timestamp;
    if(t > 604800000){
        var that = new Date(timestamp);
        var y = that.getFullYear(),
            m = that.getMonth() + 1,
            d = that.getDay(),
            hh = that.getHours(),
            mm = that.getMinutes();
        s = y===today.getFullYear() ? '' : y + '年';
        s = s + m + '月' + d + '日' + hh + ':' + (mm < 10 ? '0' : '') + mm;
    }
    else if(t >= 86400000){
        // 1-6 days ago:
        s = Math.floor(t / 86400000) + '天前';
    }
    else if(t >= 3600000){
        s = Math.floor(t / 3600000) + '小时前';
    }
    else if(t >= 60000){
        s = Math.floor(t / 60000) + '分钟前';
    }
    return s;
}


$(function () {
    $('.x-smartdate').each(function () {
        $(this).removeClass('x-smartdate').text(toSmartDate($(this).attr('date')));
    });
});



function Template(tpl) {
    var fn, match,
        code = ['var r=[];\nvar _html = function(str){return str.replace(/&/g, \'&amp;\').replace(/"/g, \'&quto;\').replace(/\'/g, \'&#39;\').replace(/</g, \'&lt;\').replace(/>/g, \'&gt;\');};'],
        re = /\{\s*([a-zA-Z\.\_0-9()]+)(\s*\|\s*safe)?\s*\}/m,
        addLine = function (text) {
            code.push('r.push(\'' + text.replace(/\'/g, '\\\'').replace(/\n/g, '\\n').replace(/\r/g, '\\r') + '\');');
        };
    while (match = re.exec(tpl)){
        if(match.index > 0){
            addLine(tpl.slice(0, match.index));
        }
        if(match[2]){
            code.push('r.push(String(this.' + match[1] + '));');
        }
        else {
            code.push('r.push(_html(String(this.' + match[1] + ')));');
        }
        tpl = tpl.substring(match.index + match[0].length);
    }
    addLine(tpl);
    code.push('return r.join(\'\');');
    fn = new Function(code.join('\n'));
    this.render = function (model) {
        return fn.apply(model);
    };
}



$(function () {
    console.log('Extends $from...');
    $.fn.extend({
        showFormError : function (err) {
            return this.each(function () {
                var $form = $(this),
                $alert = $form && $form.find('.uk-alert-danger'),
                    fieldName = err && err.data;
                if(!$form.is('form')){
                    console.error('cannot call showFormError() on non-form object.');
                    return;
                }
                $form.find('input').removeClass('uk-form-danger');
                $form.find('select').removeClass('uk-form-danger');
                $form.find('textarea').removeClass('uk-form-danger');
                if($alert.length === 0){
                    console.warn('Cannot find .uk-alert-danger element.');
                    return;
                }
                if(err){
                    $alert.text(err.message ? err.message : (err.error ? err.error : err)).removeClass('uk-hidden').show();
                    if(($alert.offset().top() - 60) < $(window).scrollTop()){
                        $('html,body').animate({scrollTop : $alert.offset().top - 60});
                    }
                    if(fieldName){
                        $form.find('[name' + fieldName + ']').addClass('uk-form-danger');
                    }
                }
                else {
                    $alert.addClass('uk-hidden').hide();
                    $form.find('.uk-form-danger').removeClass('uk-form-danger');
                }
            });
        },
        showFormLoading : function (isLoading) {
            return this.each(function () {
                var $form = $(this),
                    $submit = $form && $form.find('button[type=submit]'),
                    $buttons = $form && $form.find('button');
                    $i = $submit && $submit.find('i'),
                    iconClass = $i && $i.attr('class');
                if(!$form.is('form')){
                    console.error('Cannot call showFormLoading() on non-form object.');
                    return;
                }
                if(!iconClass || iconClass.indexOf('uk-icon')< 0){
                    console.warn('Icon < i class="uk-icon-*>" not found.');
                    return;
                }
                if(isLoading){
                    $buttons.attr('disabled', 'disabled');
                    $i && $i.addClass('uk-icon-spinner').addClass('uk-icon-spin');
                }
                else {
                    $buttons.removeAttr('disabled');
                    $i && $i.removeClass('uk-icon-spinner').removeClass('uk-icon-spin');
                }
            });
        },
        postJSON : function (url, data, callback) {
            if(arguments.length === 2){
                callback = data;
                data = {};
            }
            return this.each(function () {
                var $form = $(this);
                $form.showFormError();
                $form.showFormLoading(true);
                _httpJSON('POST', url, data, function (err, r) {
                    if(err){
                        $form.showFormError(err);
                    }
                    callback && callback(err, r);
                });
            });
        }
    });
});



function _httpJSON(method, url, data, callback) {
    var opt = {
        type : method,
        dataType : 'json'
    };
    if(method === 'GET'){
        opt.url = url + '?' + data;
    }
    if(method === 'POST'){
        opt.url = url;
        opt.data = JSON.stringify(data || {});
        opt.contentType = 'application/json';
    }
    $.ajax(opt).done(function (r) {
        if(r && r.error){
            return callback(r);
        }
        return callback(null, r);
    }).fail(function (jqXHR, textStatus) {
        return callback({'error' : 'http_bad_response', 'data' : '' + jqXHR.status, 'message' : '网络好像出问题了(HTTP ' + jqXHR.status + ')'});
    });
}


function getJSON(url, data, callback) {
    if(arguments.length === 2){
        callback = data;
        data = {};
    }
    if(typeof (data) === 'object'){
        var arr = [];
        $.each(data, function (k, v) {
            arr.push(k + '=' + encodeURIComponent(v));
        });
        data = arr.join('&');
    }
    _httpJSON('GET', url, data, callback);
}



function postJSON(url, data, callback) {
    if(arguments.length === 2){
        callback = data;
        data = {};
    }
    _httpJSON('POST', url, data, callback);
}



if(typeof (Vue)!=='undefined'){
    Vue.filter('datetime', function (value) {
        var d = value;
        if(typeof (value) === 'number'){
            d = new Date(value * 1000);
        }
        return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate() + ' ' + d.getHours() + ':' + d.getMinutes();
    });
    Vue.component('vc-pagination', {
        props : ['p'],
        template : '<ul class="uk-pagination">' +
                '<li v-if="! p.has_pre" class="uk-disabled"><span><i class="uk-icon-angle-double-left"></i></span></li>' +
                '<li v-else><a @click.prevent="gotoPage(p.page_index-1)" href="#"><i class="uk-icon-angle-double-left"></i></a></li>' +
                '<li class="uk-active"><span v-if="p.page_index == 1" v-text="1"></span>' +
                '<a v-else @click.prevent="gotoPage(1)" href="#" v-text="1"></a></li>' +
                '<li v-if="pl[0] > 2"><span>...</span></li>' +
                '<li class="uk-active" v-for="pn in pl"><span v-if="pn == p.page_index" v-text="p.page_index"></span>' +
                '<a v-else @click.prevent="gotoPage(pn)" href="#" v-text="pn"></a>' +
                '</li>' +
                '<li v-if="pl[p.page_show-1] < (p.page_count-1)"><span>...</span></li>' +
                '<li class="uk-active"><span v-if="(p.page_index == p.page_count) && (p.page_count != 1)" v-text="p.page_count"></span>' +
                '<a v-if="(p.page_index != p.page_count) && (p.page_count != 1) && (p.item_count != 0)" @click.prevent="gotoPage(p.page_count)" href="#" v-text="p.page_count"></a></li>' +
                '<li v-if="! p.has_next" class="uk-disabled"><span><i class="uk-icon-angle-double-right"></i></span></li>' +
                '<li v-else><a @click.prevent="gotoPage(p.page_index+1)" href="#"><i class="uk-icon-angle-double-right"></i></a></li>' +
                '</ul>',
        computed : {
            pl : function () {
                var left = 2;
                var right = this.p.page_count;
                var l = [];
                if(this.p.page_count > this.p.page_show){
                    left = this.p.page_index - parseInt(this.p.page_show/2);
                    if(left < 2){
                        left = 2;
                    }
                    right = left + this.p.page_show;
                    if(right > this.p.page_count){
                        right = this.p.page_count;
                        left = right - this.p.page_show;
                    }
                }
                while (left < right){
                    l.push(left);
                    left++;
                }
                return l;
            }
        },
        methods : {
            gotoPage : function (page) {
                this.$dispatch('child-page', page);
            }
        }
    });
}



function redirect(url) {
    var hash_pos = url.indexOf('#'),
        query_pos = url.indexOf('?'),
        hash = '';
    if(hash_pos >= 0){
        hash = url.substring(hash_pos);
        url = url.substring(0, hash_pos);
    }
    url = url + (query_pos >= 0 ? '&' : '?') + 't=' + new Date().getTime() + hash;
    console.log('redirect to: ' + url);
    location.assign(url);
}


function _bindSubmit($form) {
    $form.submit(function (event) {
        event.preventDefault();
        showFormError($form, null);
        var fn_error = $form.attr('fn-error'),
            fn_seccess = $form.attr('fn-success'),
            fn_data = fn_data ? window[fn_data]($form) : $form.serialize();
        var $submit = $form.find('button[type=submit]'),
            $i = $submit.find('i'),
        iconClass = $i.attr('class');
        if(!iconClass || iconClass.indexOf('uk-icon') < 0){
            $i = undefined;
        }
        $submit.attr('disabled', 'disabled');
        $i && $i.addClass('uk-icon-spinner').addClass('uk-icon-spin');
        postJSON($form.attr('action-url'), data, function (err, result) {
            $i && $i.removeClass('uk-icon-spinner').removeClass('uk-icon-spin');
            if(err){
                console.log('postJSON failed:' + JSON.stringify(err));
                $submit.removeAttr('disabled');
                fn_error ? fn_error() : showFormError($form, err);
            }
            else {
                var r = fn_success ? window[fn_success](result) : false;
                if(r === false){
                    $submit.removeAttr('disabled');
                }
            }
        });
    });
    $form._find('button[type=submit]').removeAttr('disabled');
}



$(function () {
    $('form').each(function () {
        var $form = $this();
        if($form.attr('actiion-url')){
            _bindSubmit($form);
        }
    });
});




$(function () {
    $(window).scroll(function () {
        if($(this).scrollTop() >= $(this).height/2){
            $('.goto-top').fadeIn();
        }
        else {
            $('.goto-top').fadeOut();
        }
    });
});



$(function () {
    var navItem = $('#navbar ul.uk-navbar-nav.uk-hidden-small li');
    var i = 0;
    for(i = 1; i < navItem.length; i++){
        var a = $(navItem[i]).find('a');
        if(location.pathname.indexOf(a.attr('href'))!=-1){
            $(navItem[i]).addClass('uk-active');
            break;
        }
    }
    if(i == navItem.length){
        $(navItem[0]).addClass('uk-active');
    }
});




function _display_error($obj, err) {
    if($obj.is(':visible')){
        $obj.hide();
    }
    var msg = err.message || String(err);
    var L = ['<div class="uk-alert uk-alert-danger">'];
    L.push('<p>Error: ');
    L.push(msg);
    L.push('</p><p>Code: ');
    L.push(err.error || '500');
    L.push('</p></div>');
    $obj.html(L.join('')).slideDown();
}



function error(err) {
    _display_error($('#loading'), err);
}