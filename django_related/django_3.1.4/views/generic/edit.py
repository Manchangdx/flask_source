from django.core.exceptions import ImproperlyConfigured
from django.forms import models as model_forms
from django.http import HttpResponseRedirect
from django.views.generic.base import ContextMixin, TemplateResponseMixin, View
from django.views.generic.detail import (
    BaseDetailView, SingleObjectMixin, SingleObjectTemplateResponseMixin,
)


class FormMixin(ContextMixin):
    """Provide a way to show and handle a form in a request."""
    initial = {}
    form_class = None
    success_url = None
    prefix = None

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        return self.initial.copy()

    def get_prefix(self):
        """Return the prefix to use for forms."""
        return self.prefix

    def get_form_class(self):
        """获取并返回表单类
        """
        # self 是视图类的实例
        # 该属性定义在项目中的视图类中，属性值是表单类
        return self.form_class

    def get_form(self, form_class=None):
        """创建并返回表单类的实例
        """
        if form_class is None:
            # 下面这个 get_form_class 调用的可能是当前模块在的 ModelFormMixin 类中的方法，返回值是表单类
            form_class = self.get_form_class()
        # self.get_form_kwargs 方法定义在当前模块的 ModelFormMixin 类中，返回值是字典对象
        # 表单类实例的初始化在 django.forms.models.BaseModelForm.__init__ 方法中完成
        return form_class(**self.get_form_kwargs())

    def get_form_kwargs(self):
        """从「请求对象」的 POST 属性中获取请求表单数据并返回字典对象
        """
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
        }

        if self.request.method in ('POST', 'PUT'):
            print('【django.views.generic.edit.FormMixin.get_from_kwargs】从「请求对象」的 POST 属性中获取请求表单数据')
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if not self.success_url:
            raise ImproperlyConfigured("No URL to redirect to. Provide a success_url.")
        return str(self.success_url)  # success_url may be lazy

    def form_valid(self, form):
        """If the form is valid, redirect to the supplied URL."""
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        """If the form is invalid, render the invalid form."""
        # self 是视图类的实例，form 是表单类的实例
        # self.get_context_data 就在下面，返回值是字典
        # self.render_to_response 定义在 django.views.generic.base.TemplateResponseMixin 类中
        # 此方法返回「响应对象」
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        """Insert the form into the context dict."""
        # self 是视图类的实例
        if 'form' not in kwargs:
            # self.get_form 方法定义在当前类中，返回值是表单类的实例
            kwargs['form'] = self.get_form()
        # 此父类方法返回字典对象，里面有两组键值对：
        # 'form': 表单类实例
        # 'view': 视图类实例
        kw = super().get_context_data(**kwargs)
        return kw


class ModelFormMixin(FormMixin, SingleObjectMixin):
    """Provide a way to show and handle a ModelForm in a request."""
    fields = None

    def get_form_class(self):
        """返回表单类
        """
        if self.fields is not None and self.form_class:
            raise ImproperlyConfigured(
                "Specifying both 'fields' and 'form_class' is not permitted."
            )
        if self.form_class:
            return self.form_class
        else:
            if self.model is not None:
                # If a model has been explicitly provided, use it
                model = self.model
            elif getattr(self, 'object', None) is not None:
                # If this view is operating on a single object, use
                # the class of that object
                model = self.object.__class__
            else:
                # Try to get a queryset and extract the model class
                # from that
                model = self.get_queryset().model

            if self.fields is None:
                raise ImproperlyConfigured(
                    "Using ModelFormMixin (base class of %s) without "
                    "the 'fields' attribute is prohibited." % self.__class__.__name__
                )

            return model_forms.modelform_factory(model, fields=self.fields)

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        if hasattr(self, 'object'):
            kwargs.update({'instance': self.object})
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if self.success_url:
            url = self.success_url.format(**self.object.__dict__)
        else:
            try:
                url = self.object.get_absolute_url()
            except AttributeError:
                raise ImproperlyConfigured(
                    "No URL to redirect to.  Either provide a url or define"
                    " a get_absolute_url method on the Model.")
        return url

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save()
        return super().form_valid(form)


class ProcessFormView(View):
    """Render a form on GET and processes it on POST."""
    def get(self, request, *args, **kwargs):
        """Handle GET requests: instantiate a blank version of the form."""
        # self 是视图类的实例
        # self.get_context_data 定义在当前模块下的 FormMixin 类中
        # 此方法返回字典对象，里面有两组键值对：
        # 'form': 表单类实例
        # 'view': 视图类实例，也就是 self
        # self.render_to_response 定义在 django.views.generic.base.TemplateResponseMixin 类中
        # 此方法返回「响应对象」
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        # self 是视图类的实例
        # 此方法定义在当前模块中的 FormMixin 类中，创建并返回表单类的实例
        form = self.get_form()
        # 此方法定义在 django.forms.forms.BaseForm 类中
        # 如果 POST 请求携带的表单数据被顺利解析并且表单验证器验证全部通过，返回 True
        if form.is_valid():
            # 通常情况下 self.form_valid 方法定义在项目中的自定义视图类中
            # 将调用表单类实例的某些方法创建映射类实例并将其存入数据库，最后返回的是「响应对象」
            return self.form_valid(form)
        else:
            # 此方法定义在当前模块的 FormMixin 类中，返回值是「响应对象」
            return self.form_invalid(form)

    # PUT is a valid HTTP verb for creating (with a known URL) or editing an
    # object, note that browsers only support POST for now.
    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)


class BaseFormView(FormMixin, ProcessFormView):
    """A base view for displaying a form."""


class FormView(TemplateResponseMixin, BaseFormView):
    """A view for displaying a form and rendering a template response."""


class BaseCreateView(ModelFormMixin, ProcessFormView):
    """
    Base view for creating a new object instance.

    Using this base class requires subclassing to provide a response mixin.
    """
    def get(self, request, *args, **kwargs):
        self.object = None
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = None
        return super().post(request, *args, **kwargs)


class CreateView(SingleObjectTemplateResponseMixin, BaseCreateView):
    """
    View for creating a new object, with a response rendered by a template.
    """
    template_name_suffix = '_form'


class BaseUpdateView(ModelFormMixin, ProcessFormView):
    """
    Base view for updating an existing object.

    Using this base class requires subclassing to provide a response mixin.
    """
    def get(self, request, *args, **kwargs):
        # 映射类实例
        self.object = self.get_object() 
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


class UpdateView(SingleObjectTemplateResponseMixin, BaseUpdateView):
    """View for updating an object, with a response rendered by a template."""
    template_name_suffix = '_form'


class DeletionMixin:
    """Provide the ability to delete objects."""
    success_url = None

    def delete(self, request, *args, **kwargs):
        """
        Call the delete() method on the fetched object and then redirect to the
        success URL.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.delete()
        return HttpResponseRedirect(success_url)

    # Add support for browsers which only accept GET and POST for now.
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def get_success_url(self):
        if self.success_url:
            return self.success_url.format(**self.object.__dict__)
        else:
            raise ImproperlyConfigured(
                "No URL to redirect to. Provide a success_url.")


class BaseDeleteView(DeletionMixin, BaseDetailView):
    """
    Base view for deleting an object.

    Using this base class requires subclassing to provide a response mixin.
    """


class DeleteView(SingleObjectTemplateResponseMixin, BaseDeleteView):
    """
    View for deleting an object retrieved with self.get_object(), with a
    response rendered by a template.
    """
    template_name_suffix = '_confirm_delete'
