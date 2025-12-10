from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable, Iterator
from itertools import chain
from typing import Any, TextIO, TypeAlias

Props: TypeAlias = dict[str, int | str | None]
StepMap: TypeAlias = dict[int, list[int]]
BlockConstructor: TypeAlias = Callable[[int, "Lines"], "Block"]

ELTYPES: set[str] = {
    "POINTS",
    "BEAMS",
    "QUADS",
    "TRIANGLES",
    "HEXAHEDRONS",
    "TETRAHEDRONS",
    "PENTAHEDRONS",
}


class Lines:
    f: TextIO
    queue: deque[str]

    def __init__(self, f: TextIO) -> None:
        self.f = f
        self.queue = deque()

    def __iter__(self) -> Iterator[str]:
        return self

    def until_empty(self) -> Iterator[str]:
        for line in self:
            line = line.strip()
            if not line:
                break
            yield line

    def __next__(self) -> str:
        while True:
            return self.queue.pop() if self.queue else next(self.f)

    def put_back(self, line: str) -> None:
        self.queue.append(line)


class Block:
    blkid: int

    def __init__(self, blkid: int) -> None:
        self.blkid = blkid


class InternalString(Block):
    value: str

    def __init__(self, blkid: int, lines: Lines) -> None:
        super().__init__(blkid)
        self.value = ""
        for line in lines.until_empty():
            self.value += line + "\n"


class Nodes(Block):
    def __init__(self, blkid: int, lines: Lines) -> None:
        super().__init__(blkid)
        self.npts, self.dim = check_array(lines, float, name=f"Nodes block {blkid}")


class Elements(Block):
    props: Props
    nelems: list[int]
    nverts: list[int]

    def __init__(self, blkid: int, lines: Lines) -> None:
        super().__init__(blkid)
        self.props = properties(lines, skip_on=ELTYPES)
        self.nelems = []
        self.nverts = []

        while True:
            line = next(lines)
            elemtype = line.removeprefix("%").strip().upper()
            if elemtype in ELTYPES:
                nelems, nverts = check_array(lines, int, name=f"Elements block {blkid}")
                self.nelems.append(nelems)
                self.nverts.append(nverts)
            else:
                lines.put_back(line)
                break

    @property
    def nodes_id(self) -> int:
        value = self.props["nodes"]
        assert isinstance(value, int)
        return value


class Results(Block):
    def __init__(self, blkid: int, lines: Lines):
        super().__init__(blkid)
        self.props = properties(lines)
        self.npts, self.dim = check_array(lines, float, name=f"Results block {blkid}")
        assert self.dim == self.props["dimension"], f"Result block {blkid}: Inconsistent dimension"

    @property
    def kind(self) -> str:
        if "per_node" in self.props:
            return "nodal"
        if "per_element" in self.props:
            return "element"
        raise AssertionError(f"Result block {self.blkid}: Unknown type")

    @property
    def target(self) -> int:
        value = self.props["per_node"] if self.kind == "nodal" else self.props["per_element"]
        assert isinstance(value, int)
        return value


class Steppable(Block):
    mapping: StepMap

    @property
    def maxstep(self) -> int:
        return max(self.mapping)

    @property
    def nsteps(self) -> int:
        return len(self.mapping)

    def mapping_at(self, stepid: int) -> list[int]:
        if stepid < min(self.mapping):
            return []
        while stepid not in self.mapping:
            stepid -= 1
        return self.mapping[stepid]


class Geometry(Steppable):
    def __init__(self, blkid: int, lines: Lines) -> None:
        super().__init__(blkid)
        stepid: int | None = None
        mapping: StepMap = {}
        for line in lines.until_empty():
            if line.startswith("%STEP"):
                stepid = int(line.split()[-1])
            elif line.startswith("%ELEMENTS"):
                assert stepid is not None
                mapping[stepid] = []
            else:
                assert stepid is not None
                mapping[stepid].extend(int(v.strip()) for v in line.split(",") if v.strip())
        self.mapping = mapping


class Field(Steppable):
    props: Props

    def __init__(self, blkid: int, lines: Lines) -> None:
        super().__init__(blkid)
        self.props, self.mapping = field_properties(lines)

    @property
    def name(self) -> str:
        value = self.props.get("name", "{{UNNAMED}}")
        assert isinstance(value, str)
        return value


class Displacement(Field):
    pass


class Scalar(Field):
    pass


class Vector(Field):
    pass


def check_array(
    lines: Lines,
    predicate: Callable[[str], Any],
    name: str = "Unknown location",
) -> tuple[int, int]:
    nrows = 0
    ncols: int | None = None
    for line in lines.until_empty():
        if line.startswith("%"):
            lines.put_back(line)
            break
        ncoords = len([predicate(v) for v in line.split()])
        if ncols is None:
            ncols = ncoords
        else:
            assert ncoords == ncols, f"{name}: Inconsistent dimension"
        nrows += 1
    assert ncols is not None
    return nrows, ncols


def clean_properties(props: Props) -> Props:
    new_props: Props = {}
    for name, value in props.items():
        if isinstance(value, str):
            if value.startswith("#"):
                value = int(value[1:])
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

        if isinstance(value, str):
            try:
                new_props[name] = int(value)
                continue
            except (ValueError, TypeError):
                pass
        new_props[name] = value

    return new_props


def field_properties(lines: Lines) -> tuple[Props, StepMap]:
    """Parse a field block."""
    props: Props = {}
    mapping: StepMap = {}
    stepping = False

    for line in lines.until_empty():
        if line.startswith("%STEP"):
            stepping = True

        if not stepping:
            assert line.startswith("%")
            try:
                name, value = line[1:].split(maxsplit=1)
                props[name.lower()] = value
            except ValueError:
                props[line[1:].lower()] = None

        if stepping and line.startswith("%STEP"):
            stepid = int(line.split()[-1])
            mapping[stepid] = []
        elif stepping:
            mapping[stepid].extend(int(v.strip()) for v in line.split(",") if v.strip())

    return clean_properties(props), mapping


def properties(lines: Lines, skip_on: set[str] | None = None) -> Props:
    """Split a block into properties and contents."""
    props: Props = {}

    for line in lines:
        if line.startswith("%"):
            if skip_on and line.removeprefix("%").strip().upper() in skip_on:
                lines.put_back(line)
                return clean_properties(props)

            try:
                name, value = line[1:].split(maxsplit=1)
                props[name.lower()] = value
            except ValueError:
                props[line[1:].lower()] = None

        else:
            lines.put_back(line)
            break

    return clean_properties(props)


def blocks(f: TextIO) -> Iterator[Block]:
    """Yield all blocks in a file."""
    warnings: set[str] = {"glviewstateinfo"}
    classes: dict[str, BlockConstructor] = {
        "internalstring": InternalString,
        "nodes": Nodes,
        "elements": Elements,
        "results": Results,
        "glviewgeometry": Geometry,
        "glviewdisplacement": Displacement,
        "glviewscalar": Scalar,
        "glviewvector": Vector,
    }

    try:
        line = next(f)
        assert line.startswith("*VTF-"), "File is not a valid ASCII VTF file"
    except UnicodeDecodeError:
        raise AssertionError("File is not a valid ASCII VTF file")

    lines = Lines(f)
    for line in lines:
        if line.startswith("*"):
            block_type, block_id_str = line[1:].split()
            block_type = block_type.lower()
            block_id = int(block_id_str)
            if block_type in classes:
                yield classes[block_type](block_id, lines)
            elif block_type not in warnings:
                print(f"WARNING: Ignoring {block_type} block")
                warnings.add(block_type)


class VTFFile:
    strings: dict[int, InternalString]
    nodes: dict[int, Nodes]
    elements: dict[int, Elements]
    results: dict[int, Results]
    geometry: Geometry | None
    displacements: dict[int, Displacement]
    scalars: dict[int, Scalar]
    vectors: dict[int, Vector]

    def __init__(self, f: TextIO) -> None:
        self.nodes = {}
        self.strings = {}
        self.elements = {}
        self.results = {}
        self.displacements = OrderedDict()
        self.scalars = OrderedDict()
        self.vectors = OrderedDict()
        self.geometry = None

        for block in blocks(f):
            if isinstance(block, InternalString):
                self.strings[block.blkid] = block
            elif isinstance(block, Nodes):
                self.nodes[block.blkid] = block
            elif isinstance(block, Elements):
                self.elements[block.blkid] = block
            elif isinstance(block, Results):
                self.results[block.blkid] = block
            elif isinstance(block, Geometry):
                assert self.geometry is None, "Multiple geometry blocks"
                self.geometry = block
            elif isinstance(block, Displacement):
                self.displacements[block.blkid] = block
            elif isinstance(block, Scalar):
                self.scalars[block.blkid] = block
            elif isinstance(block, Vector):
                self.vectors[block.blkid] = block
            else:
                raise Exception(type(block))

    def fields(self) -> Iterator[Field]:
        return chain(self.displacements.values(), self.scalars.values(), self.vectors.values())

    def verify(self) -> None:
        for blkid, elems in self.elements.items():
            assert elems.nodes_id in self.nodes, (
                f"Elements block {blkid}: Unknown nodes block {elems.nodes_id}"
            )

        for blkid, results in self.results.items():
            if results.kind == "nodal":
                assert results.target in self.nodes, (
                    f"Results block {blkid}: Unknown nodes block {results.target}"
                )
                assert results.npts == self.nodes[results.target].npts, (
                    "Results block {blkid}: Incorrect size"
                )
            if results.kind == "element":
                assert results.target in self.elements, (
                    f"Results block {blkid}: Unknown elements block {results.target}"
                )
                assert results.npts == sum(self.elements[results.target].nelems), (
                    f"Results block {blkid}: Incorrect size"
                )

        if self.geometry is None:
            raise AssertionError("Geometry block missing")
        for step in self.geometry.mapping.values():
            for blkid in step:
                assert blkid in self.elements, f"Geometry block points to unknown elements block {blkid}"

        for field in self.fields():
            name = field.__class__.__name__
            for step in field.mapping.values():
                for blkid in step:
                    assert blkid in self.results, (
                        f"{name} block {field.blkid}: Points to unknown results block {blkid}"
                    )

    def summary(self) -> None:
        assert self.geometry is not None
        nsteps = max(b.maxstep for b in chain([self.geometry], self.fields()))

        for stepid in range(1, nsteps + 1):
            print(f"Step {stepid}")

            eblks = [self.elements[blkid] for blkid in self.geometry.mapping_at(stepid)]
            nblks = [self.nodes[eblk.nodes_id] for eblk in eblks]
            for gpart, (eblk, nblk) in enumerate(zip(eblks, nblks), start=1):
                nelems = ", ".join(str(n) for n in eblk.nelems)
                print(f"  Element block {gpart}")
                print(f"    {nblk.npts} nodes")
                print(f"    {nelems} elements")

                for field in self.fields():
                    # Check if this field is defined on this geometry part at this step
                    rblks = [self.results[blkid] for blkid in field.mapping_at(stepid)]

                    found = any(
                        (rblk.kind == "nodal" and rblk.target == nblk.blkid)
                        or (rblk.kind == "element" and rblk.target == eblk.blkid)
                        for rblk in rblks
                    )

                    # Only print if found
                    if found:
                        print(f"    {field.__class__.__name__}: '{field.name}'")
