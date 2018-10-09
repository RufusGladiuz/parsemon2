"""Contains the implementation of the parser monad.  This module is not intended
to be used from outside this library
"""


from copy import copy
from typing import Callable, Generic, Sized, Tuple, TypeVar

from attr import attrib, attrs, evolve
from parsemon.error import ParsingFailed
from parsemon.sourcemap import (display_location, find_line_in_indices,
                                find_linebreak_indices)
from parsemon.stack import Stack, StackEmptyError
from parsemon.trampoline import Call, Result, Trampoline

T = TypeVar('T')
S = TypeVar('S')
ParserResult = TypeVar('ParserResult')
ParserInput = TypeVar('ParserInput')


@attrs
class Parser(Generic[ParserResult, ParserInput]):
    """Parser objects that can be consumed by ParserState"""
    function: Callable[
        [ParserInput, 'ParserState'],
        Trampoline[Tuple[ParserResult, ParserInput]]
    ] = attrib()

    def __call__(
            self,
            input_value: ParserInput,
            parser_state: 'ParserState[T, ParserResult]'
    ) -> Trampoline[Tuple[ParserResult, ParserInput]]:
        return self.function(input_value, parser_state)


@attrs
class ParserState(Generic[T, ParserResult]):
    document: Sized = attrib()
    location: int = attrib()
    callbacks = attrib(default=Stack())
    choices = attrib(default=Stack())
    error_messages = attrib(default=Stack())

    def __copy__(self):
        return ParserState(
            document=self.document,
            location=self.location,
            callbacks=self.callbacks,
            choices=self.choices,
            error_messages=self.error_messages
        )

    def set_location(self, new_location):
        """Return new parsing status with document cursor set to given location.
        """
        new_state = copy(self)
        new_state.location = new_location
        return new_state

    def has_binding(self):
        """Check if there are more parsing statements to process."""
        return not self.callbacks.empty()

    def get_bind(
            self,
            value: T
    ) -> Tuple[Parser[ParserResult, Sized], 'ParserState[T, ParserResult]']:
        """Get next parser and updated parser state from previous parsing
        result.
        """
        parser_generator: Callable[[T], Parser[ParserResult, Sized]]
        parser_generator = self.callbacks.top()
        next_parser_bind = copy(self)
        next_parser_bind.callbacks = self.callbacks.pop()
        return (
            parser_generator(value),
            next_parser_bind
        )

    def add_binding(
            self,
            binding: Callable[[T], Parser[S, ParserInput]]
    ) -> 'ParserState[T, S]':
        return evolve(  # type: ignore
            self,
            callbacks=self.callbacks.push(binding)
        )

    def finally_remove_error_message(self):
        """Returns a new parser where all error messages are removed after
        succesful parsing.
        """
        def pop_error_message(value):
            return lambda rest, bindings: (
                bindings.pop_error_message().pass_result(value, rest)
            )
        return self.add_binding(pop_error_message)

    def pop_error_message(self):
        newbind = copy(self)
        newbind.error_messages = self.error_messages.pop()
        return newbind

    def push_error_message_generator(
            self,
            msg_generator: Callable[[], str]
    ):
        newbind = copy(self)
        newbind.error_messages = self.error_messages.push(msg_generator)
        return newbind

    def copy_error_messages_from(
            self,
            other: 'ParserState[T, ParserResult]'
    ) -> 'ParserState[T, ParserResult]':
        p = copy(self)
        for item in reversed(other.error_messages):
            p.push_error_message_generator(item)
        return p

    def get_error_messages(self):
        return list(self.error_messages)

    def finally_remove_choice(self):
        def pop_choice_parser(value):
            return lambda rest, bindings: (
                bindings.pop_choice().pass_result(value, rest)
            )
        return self.add_binding(pop_choice_parser)

    def add_choice(
            self,
            parser: Parser[ParserResult, str],
            rest: str
    ) -> 'ParserState[T, ParserResult]':
        newbind = copy(self)
        newbind.choices = self.choices.push((
            parser,
            rest,
            self.finally_remove_error_message()
        ))
        return newbind.finally_remove_choice()

    def pop_choice(self):
        """Return a new parser state with next choice on stack removed"""
        newbind = copy(self)
        newbind.choices = self.choices.pop()
        return newbind

    def next_choice(self):
        """Returns possibly the next choice given to the parser"""
        try:
            return self.choices.top()
        except StackEmptyError:
            return None

    def pass_result(
            self,
            value: T,
            rest: Sized,
            characters_consumed=None,
    ) -> Trampoline:
        """Signals that parsing was successful"""
        if self.has_binding():
            next_parser: 'Parser[ParserResult, Sized]'
            next_bind: 'ParserState[T, ParserResult]'

            next_parser, next_bind = self.get_bind(value)
            if characters_consumed is None:
                new_location = len(self.document) - len(rest)
            else:
                new_location = self.location + characters_consumed
            return Call(
                next_parser,
                rest,
                next_bind.set_location(new_location)
            )
        else:
            return Result((value, rest))

    @property
    def current_location(self):
        """Current location in the document that is to be parsed"""
        def do_it():
            linebreaks = find_linebreak_indices(self.document)
            line = find_line_in_indices(self.location, linebreaks)
            if linebreaks:
                column = self.location - linebreaks[line - 2] - 1
            else:
                column = self.location
            return line, column

        if hasattr(self, "_current_location"):
            return self._current_location
        self._current_location = do_it()
        return self._current_location

    def parser_failed(self, msg, exception=ParsingFailed):
        """Signals that the current parsing attempt failed.

        If possible, the we'll try again with alternatives that were provided.
        """
        def rendered_message():
            line, column = self.current_location
            return '{message} @ {location}'.format(
                message=msg,
                location=display_location(line=line, column=column)
            )
        if self.next_choice() is None:
            old_message_generators = self.get_error_messages()
            old_messages = list(map(lambda f: f(), old_message_generators))
            final_message = ' OR '.join(
                [rendered_message()] + old_messages
            )
            raise exception(final_message)
        else:
            next_parser, rest, next_bind = self.next_choice()
            return Call(
                next_parser,
                rest,
                (next_bind
                 .copy_error_messages_from(self)
                 .push_error_message_generator(rendered_message))
            )
