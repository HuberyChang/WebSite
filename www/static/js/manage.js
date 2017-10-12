function initVM(def) {
    var vm = new Vue({
        el: '#vm',
        data: {
            items: def.items,
            page: def.page,
            currentPage: def.currentPage,
            table: def.table
        },
        ready: function () {
            this.setItems(1);
        },
        methods: {
            setItems: function (p) {
                var self = this;
                this.items = {};
                $('#loading').show();
                getJSON('/api/manage/' + this.table, { page: p }, function (err, res) {
                    if (err) {
                        return fatal(err);
                    }
                    $('#loading').hide();
                    if ('blog' == self.table) {
                        self.items = res.blogs;
                    } else if ('comment' == self.table) {
                        self.items = res.comments;
                    } else if ('user' == self.table) {
                        self.items = res.users;
                    } else if ('category' == self.table) {
                        self.items = res.categories;
                    }
                    self.page = res.page;
                });
            },
            nav_blog: function () {
                this.table = 'blog';
                $('#nav_blog').addClass('uk-active');
                $('#nav_cmt').removeClass('uk-active');
                $('#nav_user').removeClass('uk-active');
                $('#nav_cat').removeClass('uk-active');
                $("#create_btn").attr("href", "/manage/blog/create");
                $('#create_btn').html('<i class="uk-icon-plus"></i> 新建文章');
                $('#create_btn').show();
                this.setItems(1);
            },
            nav_cmt: function () {
                this.table = 'comment';
                $('#nav_cmt').addClass('uk-active');
                $('#nav_blog').removeClass('uk-active');
                $('#nav_user').removeClass('uk-active');
                $('#nav_cat').removeClass('uk-active');
                $("#create_btn").attr("href", "#");
                $('#create_btn').hide();
                this.setItems(1);
            },
            nav_user: function () {
                this.table = 'user';
                $('#nav_user').addClass('uk-active');
                $('#nav_blog').removeClass('uk-active');
                $('#nav_cmt').removeClass('uk-active');
                $('#nav_cat').removeClass('uk-active');
                $("#create_btn").attr("href", "#");
                $('#create_btn').hide();
                this.setItems(1);
            },
            nav_cat: function () {
                this.table = 'category';
                $('#nav_cat').addClass('uk-active');
                $('#nav_blog').removeClass('uk-active');
                $('#nav_user').removeClass('uk-active');
                $('#nav_cmt').removeClass('uk-active');
                $("#create_btn").attr("href", "/manage/category/create");
                $('#create_btn').html('<i class="uk-icon-plus"></i> 新建分类');
                $('#create_btn').show();
                this.setItems(1);
            },
            edit_item: function (item) {
                location.assign('/manage/' + this.table + '/edit?id=' + item.id);
            },
            delete_item: function (item) {
                var name;
                var self = this;
                switch (this.table) {
                    case 'blog':
                        name = item.title;
                        break;
                    case 'comment':
                        name = item.content.substring(0, 40);
                        break;
                    case 'user':
                        name = item.name
                        break;
                    case 'category':
                        name = item.name
                        break;
                    default:
                        name = '';
                        break;
                }
                if (confirm('确认要删除“' + name + '”？删除后不可恢复！')) {
                    postJSON('/api/' + this.table + '/' + item.id + '/delete', function (err, r) {
                        if (err) {
                            return error(err);
                        }
                        self.setItems(self.currentPage);
                    });
                }
            }
        },
        events: {
            'child-page': function (page) {
                this.setItems(page);
                this.currentPage = page;
            }
        }
    });
}

function initPage() {
    p = {};
    p.item_count = 1;
    p.page_index = 1;
    p.item_page = 10;
    p.page_show = 1;
    p.page_count = Math.floor(p.item_count / p.item_page + (p.item_count % p.item_page > 0 ? 1 : 0));
    p.offset = 0;
    p.limit = 0;
    p.has_next = false;
    p.has_pre = false;
    return p;
}

$(function() {
    var def = {};
    def.itmes = {};
    def.page = initPage();
    def.currentPage = 1;
    def.table = 'blog';
    initVM(def);
});