from functools import reduce

from attr import attrib, attrs, evolve

from .deque import Stack, deque_empty


@attrs
class CharacterStream:
    content = attrib()
    length = attrib()

    @classmethod
    def from_string(cls, content):
        return cls(
            content=reduce(
                lambda stack, character: stack.push(character),
                reversed(content),
                Stack()
            ),
            length=len(content),
        )

    def next(self):
        top_value = self.content.top()
        return None if top_value is deque_empty else top_value

    def read(self):
        return (
            self.next(),
            evolve(
                self,
                content=self.content.pop(),
                length=(
                    self.length
                    if self.content.empty()
                    else self.length - 1
                ),
            )
        )

    def __len__(self):
        return self.length

    def to_string(self):
        return ''.join(self.content)


@attrs
class StringStream:
    content = attrib()
    position = attrib()
    length = attrib()

    @classmethod
    def from_string(cls, content):
        return cls(
            content,
            position=0,
            length=len(content),
        )

    def __len__(self):
        return self.length - self.position

    def to_string(self):
        return self.content[self.position:]

    def read(self):
        if self:
            return (
                self.content[self.position],
                evolve(
                    self,
                    position=self.position+1,
                )
            )
        else:
            return (
                None,
                self
            )

    def next(self):
        if self.content:
            return self.content[self.position]
        else:
            return None
