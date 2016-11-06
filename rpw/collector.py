from copy import copy
from functools import reduce

from rpw import uidoc, doc, DB
from rpw.logger import logger
from rpw.base import BaseObjectWrapper
from rpw.exceptions import RPW_Exception
from rpw.enumeration import BuiltInCategoryEnum, BuiltInParameterEnum

from System.Collections.Generic import List


class Collector(BaseObjectWrapper):
    """
    Revit FilteredElement Collector Wrapper

    Usage:
        >>> collector = Collector()
        >>> elements = collector.filter(of_class=View)

        Multiple Filters:

        >>> collector = Collector()
        >>> elements = collector.filter(of_category=BuiltInCategory.OST_Walls,
                                        is_element_type=True)

        Chain Preserves Previous Results:

        >>> collector = Collector()
        >>> walls = collector.filter(of_category=BuiltInCategory.OST_Walls)
        >>> walls.filter(is_element_type=True)

        Use Enumeration member or string shortcut:

        >>> collector.filter(of_category='OST_Walls')
        >>> collector.filter(of_category='ViewType')

    Returns:
        Collector: Returns collector Class

    Attributes:
        collector.elements: Returns list of all *collected* elements
        collector.first: Returns first found element, or `None`

    Wrapped Element:
        self._revit_object = `Revit.DB.FilteredElementCollector`

    """

    def __init__(self, **filters):
        """
        Args:
            view (Revit.DB.View) = View Scope (Optional)
        """
        if 'view' in filters:
            view = filters['view']
            collector = DB.FilteredElementCollector(doc, view.Id)
        else:
            collector = DB.FilteredElementCollector(doc)
        super(Collector, self).__init__(collector)

        self.elements = []
        self._filters = filters

        self.filter = _Filter(self)
        # Allows Class to Excecute on Construction, if filters are present.
        if filters:
            self.filter(**filters)

    @property
    def first(self):
        """ Returns the first element in collector, or None"""
        try:
            return self.elements[0]
        except IndexError:
            return None

    def __bool__(self):
        """ Evaluates to `True` if Collector.elements is not empty [] """
        return bool(self.elements)

    def __len__(self):
        """ Returns length of collector.elements """
        return len(self.elements)

    def __repr__(self):
        return super(Collector, self).__repr__(len(self))


class _Filter():
    """ Filter for Collector class.
    Not to be confused with the Filter Class.
    """
    MAP = {
             'of_class': 'OfClass',
             'of_category': 'OfCategory',
             'is_element': 'WhereElementIsNotElementType',
             'is_element_type': 'WhereElementIsElementType',
             'is_view_independent': 'WhereElementIsViewIndependent',
             'parameter_filter': 'WherePasses',
            }

    def __init__(self, collector):
        self._collector = collector

    def __call__(self, **filters):
        """
        collector = Collector().filter > ._Filter(filters)
        filters = {'of_class'=Wall}
        """
        filters = self.coerce_filter_values(filters)

        for key, value in filters.iteritems():
            self._collector._filters[key] = value

        filtered_collector = self.chain(self._collector._filters)
        # TODO: This should return iterator to save memory
        self._collector.elements = [element for element in filtered_collector]
        return self._collector

    def chain(self, filters, collector=None):
        """ Chain filters together.

        Converts this syntax: `collector.filter(of_class=X, is_element=True)`
        into: `FilteredElementCollector.OfClass(X).WhereElementisNotElementType()`

        A copy of the filters is copied after each pass so the Function
        can be called recursevily in a queue.

        """
        # First Loop
        if not collector:
            collector = self._collector._revit_object

        # Stack is track filter chainning queue
        filter_stack = copy(filters)
        for filter_name, filter_value in filters.iteritems():
            collector_filter = getattr(collector, _Filter.MAP[filter_name])

            if filter_name not in _Filter.MAP:
                raise RPW_Exception('collector filter rule does not exist: {}'.format(filter_name))

            elif isinstance(filter_value, bool):
                if filter_value is True:
                    collector_results = collector_filter()
            elif isinstance(filter_value, ParameterFilter):
                collector_results = collector_filter(filter_value._revit_object)
            else:
                collector_results = collector_filter(filter_value)
            filter_stack.pop(filter_name)
            collector = self.chain(filter_stack, collector=collector)

        return collector

    def coerce_filter_values(self, filters):
        """ Allows value to be either Enumerate or string.

        Usage:
            >>> elements = collector.filter(of_category=BuiltInCategory.OST_Walls)
            >>> elements = collector.filter(of_category='OST_Walls')

            >>> elements = collector.filter(of_class=WallType)
            >>> elements = collector.filter(of_class='WallType')

        Note:
            String Connversion for `of_class` only works for the Revit.DB
            namespace.

        """
        category_name = filters.get('of_category')
        if category_name and isinstance(category_name, str):
            filters['of_category'] = BuiltInCategoryEnum.by_name(category_name)

        class_name = filters.get('of_class')
        if class_name and isinstance(class_name, str):
            filters['of_class'] = getattr(DB, class_name)

        return filters


class ParameterFilter(BaseObjectWrapper):
    """ Parameter Filter Wrapper

    Usage:
        >>> parameter_filter = ParameterFilter('Type Name', equals='Wall 1')
        >>> collector = Collector(parameter_filter=parameter_filter)

        >>> parameter_filter = ParameterFilter('Height', less_than=10)
        >>> collector = Collector(parameter_filter=parameter_filter)

    ParameterFilterRuleFactory:
        ParameterFilterRuleFactory.CreateBeginsWithRule(param_id, value, case_sensitive)
        ParameterFilterRuleFactory.CreateContainsRule(param_id, value, case_sensitive)
        ParameterFilterRuleFactory.CreateEndsWithRule(param_id, value, case_sensitive)
        ParameterFilterRuleFactory.CreateEqualsRule(param_id, value)
        ParameterFilterRuleFactory.CreateGreaterOrEqualRule(param_id, value)
        ParameterFilterRuleFactory.CreateGreaterRule(param_id, value)
        ParameterFilterRuleFactory.CreateLessOrEqualRule(param_id, value)
        ParameterFilterRuleFactory.CreateLessRule(param_id, value)
        ParameterFilterRuleFactory.CreateNotBeginsWithRule(param_id, value)
        ParameterFilterRuleFactory.CreateNotContainsRule(param_id, value)
        ParameterFilterRuleFactory.CreateNotEqualsRule(param_id, value)
        ParameterFilterRuleFactory.CreateSharedParameterApplicableRule(param_name)

    Returns:
        FilterDoubleRule(provider, evaluator, rule_value, tolerance)
        FilterElementIdRule(provider, evaluator, ElementId)
        FilterCategoryRule(ElementId)
        FilterStringRule(provider, evaluator, string, case_sensitive)
        FilterIntegerRule(provider, evaluator, value)
        SharedParameterApplicableRule(parameter_name)

    """

    RULES = {
            'equals': 'CreateEqualsRule',
            'contains': 'CreateContainsRule',
            'begins': 'CreateBeginsWithRule',
            'ends': 'CreateEndsWithRule',
            'greater': 'CreateGreaterRule',
            'greater_equal': 'CreateGreaterOrEqualRule',
            'less': 'CreateLessRule',
            'less_equal': 'CreateLessOrEqualRule',
           }

    CASE_SENSITIVE = True
    FLOAT_PRECISION = 0.0013020833333333

    def __init__(self, parameter_id, **conditions):
        self.parameter_id = parameter_id
        self.conditions = conditions
        self.case_sensitive = conditions.get('case_sensitive', ParameterFilter.CASE_SENSITIVE)
        self.reverse = conditions.get('reverse', False)
        self.precision = conditions.get('precision', ParameterFilter.FLOAT_PRECISION)

        valid_rule = [x for x in conditions if x in ParameterFilter.RULES]
        for condition_name in valid_rule:
            condition_value = conditions[condition_name]

            # Returns on of the CreateRule factory method names above
            rule_factory_name = ParameterFilter.RULES.get(condition_name)
            filter_value_rule = getattr(DB.ParameterFilterRuleFactory, rule_factory_name)

            args = [condition_value]

            if isinstance(condition_value, str):
                args.append(self.case_sensitive)

            if isinstance(condition_value, float):
                args.append(1.0)

            logger.critical('conditions: {}'.format(conditions))
            # logger.critical('Case sensitive: {}'.format(self.case_sensitive))
            logger.critical('ARGS: {}'.format(args))
            logger.critical('Reverse: {}'.format(self.reverse))
            filter_rule = filter_value_rule(parameter_id, *args)
            logger.critical(filter_rule)
            self._revit_object = DB.ElementParameterFilter(filter_rule, self.reverse)

    def __repr__(self):
        return super(ParameterFilter, self).__repr__(self.conditions)
