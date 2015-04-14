# coding: utf-8

# python imports
from functools import wraps

# try to use json (2.6+) but stay compatible with 2.5.*
from django.contrib.admin.templatetags.admin_list import result_list, result_hidden_fields, results
from django.contrib.admin.util import label_for_field
from django.contrib.admin.views.main import ORDER_VAR
from django.utils.html import format_html

try:
    import json
except ImportError:
    from django.utils import simplejson as json

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
except ImportError:
    from django.contrib.auth.models import User

# django imports
from django import template
from django.contrib.contenttypes.models import ContentType
from django.utils.formats import get_format
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.template.loader import get_template
from django.template.context import Context

# grappelli imports
from grappelli.settings import ADMIN_TITLE, ADMIN_URL, SWITCH_USER, SWITCH_USER_ORIGINAL, SWITCH_USER_TARGET, CLEAN_INPUT_TYPES

register = template.Library()


# GENERIC OBJECTS
class do_get_generic_objects(template.Node):
    def __init__(self):
        pass

    def render(self, context):
        objects = {}
        for c in ContentType.objects.all().order_by('id'):
            objects[c.id] = {'pk': c.id, 'app': c.app_label, 'model': c.model}
        return json.dumps(objects)


@register.tag
def get_content_types(parser, token):
    """
    Returns a list of installed applications and models.
    Needed for lookup of generic relationships.
    """
    tokens = token.contents.split()
    return do_get_generic_objects()


# ADMIN_TITLE
@register.simple_tag
def get_admin_title():
    """
    Returns the Title for the Admin-Interface.
    """
    return ADMIN_TITLE


# RETURNS CURRENT LANGUAGE
@register.simple_tag
def get_lang():
    return get_language()


# ADMIN_URL
@register.simple_tag
def get_admin_url():
    """
    Returns the URL for the Admin-Interface.
    """
    return ADMIN_URL


@register.simple_tag
def get_date_format():
    return get_format('DATE_INPUT_FORMATS')[0]


@register.simple_tag
def get_time_format():
    return get_format('TIME_INPUT_FORMATS')[0]


@register.simple_tag
def get_datetime_format():
    return get_format('DATETIME_INPUT_FORMATS')[0]


@register.simple_tag
def grappelli_admin_title():
    return ADMIN_TITLE


@register.simple_tag
def grappelli_clean_input_types():
    return CLEAN_INPUT_TYPES


@register.filter
def classname(obj, arg=None):
    classname = obj.__class__.__name__.lower()
    if arg:
        if arg.lower() == classname:
            return True
        return False
    return classname


@register.filter
def classpath(obj):
    module = obj.__module__
    classname = obj.__class__.__name__
    return "%s,%s" % (module, classname)


# FORMSETSORT FOR SORTABLE INLINES

@register.filter
def formsetsort(formset, arg):
    """
    Takes a list of formset dicts, returns that list sorted by the sortable field.
    """
    if arg:
        sorted_list = []
        for item in formset:
            position = item.form[arg].data
            if position and position != "-1":
                sorted_list.append((int(position), item))
        sorted_list.sort()
        sorted_list = [item[1] for item in sorted_list]
        for item in formset:
            position = item.form[arg].data
            if not position or position == "-1":
                sorted_list.append(item)
    else:
        sorted_list = formset
    return sorted_list


# RELATED LOOKUPS

def safe_json_else_list_tag(f):
    """
    Decorator. Registers function as a simple_tag.
    Try: Return value of the decorated function marked safe and json encoded.
    Except: Return []
    """
    @wraps(f)
    def inner(model_admin):
        try:
            return mark_safe(json.dumps(f(model_admin)))
        except:
            return []
    return register.simple_tag(inner)


@safe_json_else_list_tag
def get_related_lookup_fields_fk(model_admin):
    return model_admin.related_lookup_fields.get("fk", [])


@safe_json_else_list_tag
def get_related_lookup_fields_m2m(model_admin):
    return model_admin.related_lookup_fields.get("m2m", [])


@safe_json_else_list_tag
def get_related_lookup_fields_generic(model_admin):
    return model_admin.related_lookup_fields.get("generic", [])


# AUTOCOMPLETES

@safe_json_else_list_tag
def get_autocomplete_lookup_fields_fk(model_admin):
    return model_admin.autocomplete_lookup_fields.get("fk", [])


@safe_json_else_list_tag
def get_autocomplete_lookup_fields_m2m(model_admin):
    return model_admin.autocomplete_lookup_fields.get("m2m", [])


@safe_json_else_list_tag
def get_autocomplete_lookup_fields_generic(model_admin):
    return model_admin.autocomplete_lookup_fields.get("generic", [])


# SORTABLE EXCLUDES
@safe_json_else_list_tag
def get_sortable_excludes(model_admin):
    return model_admin.sortable_excludes


@register.filter
def prettylabel(value):
    return mark_safe(value.replace(":</label>", "</label>"))


# CUSTOM ADMIN LIST FILTER
# WITH TEMPLATE DEFINITION
@register.simple_tag
def admin_list_filter(cl, spec):
    try:
        tpl = get_template(cl.model_admin.change_list_filter_template)
    except:
        tpl = get_template(spec.template)
    return tpl.render(Context({
        'title': spec.title,
        'choices': list(spec.choices(cl)),
        'spec': spec,
    }))


# HAX FIX in some cases the base name of the tag was overriden by other packages
@register.simple_tag
def admin_list_filter_custom(cl, spec):
    return admin_list_filter(cl, spec)


def extended_result_headers(cl):
    """
    Generates the list column headers taking into account collapsible header texts.
    """
    ordering_field_columns = cl.get_ordering_field_columns()
    for i, field_name in enumerate(cl.list_display):
        text, attr = label_for_field(field_name, cl.model, model_admin=cl.model_admin, return_attr=True)
        shortened_name = cl.model_admin.list_shortened_labels.get(field_name, None)
        tooltip = text if shortened_name else ''
        if shortened_name:
            text = shortened_name

        if attr:
            # Potentially not sortable
            # if the field is the action checkbox: no sorting and special class
            if field_name == 'action_checkbox':
                yield {
                    "text": text,
                    "tooltip": tooltip,
                    "class_attrib": mark_safe(' class="action-checkbox-column"'),
                    "sortable": False,
                }
                continue

            admin_order_field = getattr(attr, "admin_order_field", None)
            if not admin_order_field:
                # Not sortable
                yield {
                    "text": text,
                    "class_attrib": format_html(' class="column-{0}"', field_name),
                    "sortable": False,
                }
                continue

        # OK, it is sortable if we got this far
        th_classes = ['sortable', 'column-{0}'.format(field_name)]
        order_type = ''
        new_order_type = 'asc'
        sort_priority = 0
        sorted = False
        # Is it currently being sorted on?
        if i in ordering_field_columns:
            sorted = True
            order_type = ordering_field_columns.get(i).lower()
            sort_priority = list(ordering_field_columns).index(i) + 1
            th_classes.append('sorted %sending' % order_type)
            new_order_type = {'asc': 'desc', 'desc': 'asc'}[order_type]

        # build new ordering param
        o_list_primary = []  # URL for making this field the primary sort
        o_list_remove = []  # URL for removing this field from sort
        o_list_toggle = []  # URL for toggling order type for this field
        make_qs_param = lambda t, n: ('-' if t == 'desc' else '') + str(n)

        for j, ot in ordering_field_columns.items():
            if j == i:  # Same column
                param = make_qs_param(new_order_type, j)
                # We want clicking on this header to bring the ordering to the
                # front
                o_list_primary.insert(0, param)
                o_list_toggle.append(param)
                # o_list_remove - omit
            else:
                param = make_qs_param(ot, j)
                o_list_primary.append(param)
                o_list_toggle.append(param)
                o_list_remove.append(param)

        if i not in ordering_field_columns:
            o_list_primary.insert(0, make_qs_param(new_order_type, i))

        yield {
            "text": text,
            "tooltip": tooltip,
            "sortable": True,
            "sorted": sorted,
            "ascending": order_type == "asc",
            "sort_priority": sort_priority,
            "url_primary": cl.get_query_string({ORDER_VAR: '.'.join(o_list_primary)}),
            "url_remove": cl.get_query_string({ORDER_VAR: '.'.join(o_list_remove)}),
            "url_toggle": cl.get_query_string({ORDER_VAR: '.'.join(o_list_toggle)}),
            "class_attrib": format_html(' class="{0}"', ' '.join(th_classes)) if th_classes else '',
        }


@register.inclusion_tag("admin/change_list_results.html")
def result_list_custom(cl):
    """
    Displays the headers and data list together
    """
    headers = list(extended_result_headers(cl))
    num_sorted_fields = 0
    for h in headers:
        if h['sortable'] and h['sorted']:
            num_sorted_fields += 1
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': headers,
            'num_sorted_fields': num_sorted_fields,
            'results': list(results(cl))}


@register.simple_tag(takes_context=True)
def switch_user_dropdown(context):
    if SWITCH_USER:
        tpl = get_template("admin/includes_grappelli/switch_user_dropdown.html")
        request = context["request"]
        session_user = request.session.get("original_user", {"id": request.user.id, "username": request.user.username})
        try:
            original_user = User.objects.get(pk=session_user["id"], is_staff=True)
        except User.DoesNotExist:
            return ""
        if SWITCH_USER_ORIGINAL(original_user):
            object_list = [user for user in User.objects.filter(is_staff=True).exclude(pk=original_user.pk) if SWITCH_USER_TARGET(original_user, user)]
            return tpl.render(Context({
                'request': request,
                'object_list': object_list,
            }))
    return ""
