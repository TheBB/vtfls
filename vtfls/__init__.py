from collections import namedtuple
from itertools import takewhile, chain
from operator import methodcaller


Nodes = namedtuple('Nodes', ['npts', 'dim'])
Elements = namedtuple('Elements', ['nodes_id', 'name', 'part_id'])


class Block:

    def __init__(self, blkid):
        self.blkid = blkid


class InternalString(Block):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        self.value = ''
        for line in lines:
            self.value += line + '\n'


class Nodes(Block):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        self.npts, self.dim = check_array(lines, float, name='Nodes block {}'.format(blkid))


class Elements(Block):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        props, lines = properties(lines)
        self.props = props
        self.nelems, self.nverts = check_array(lines, int, name='Elements block {}'.format(blkid))

    @property
    def nodes_id(self):
        return self.props['nodes']


class Results(Block):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        props, lines = properties(lines)
        self.props = props
        self.npts, self.dim = check_array(lines, float, name='Results block {}'.format(blkid))
        assert self.dim == props['dimension'], 'Result block {}: Inconsistent dimension'.format(blkid)

    @property
    def kind(self):
        if 'per_node' in self.props:
            return 'nodal'
        elif 'per_element' in self.props:
            return 'element'
        raise AssertionError('Result block {}: Unknown type'.format(self.blkid))

    @property
    def target(self):
        return self.props['per_node'] if self.kind == 'nodal' else self.props['per_element']


class Steppable(Block):

    @property
    def maxstep(self):
        return max(self.mapping)

    @property
    def nsteps(self):
        return len(self.mapping)

    def mapping_at(self, stepid):
        if stepid < min(self.mapping):
            return []
        while stepid not in self.mapping:
            stepid -= 1
        return self.mapping[stepid]


class Geometry(Steppable):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        stepid, mapping = None, {}
        for line in lines:
            if line.startswith('%STEP'):
                stepid = int(line.split()[-1])
            elif line.startswith('%ELEMENTS'):
                mapping[stepid] = []
            else:
                mapping[stepid].extend(int(v.strip()) for v in line.split(',') if v.strip())
        self.mapping = mapping


class Field(Steppable):

    def __init__(self, blkid, lines):
        super().__init__(blkid)
        self.props, self.mapping = field_properties(lines)

    @property
    def name(self):
        return self.props['name']


class Displacement(Field):
    pass

class Scalar(Field):
    pass

class Vector(Field):
    pass


def check_array(lines, predicate, name='Unknown location'):
    nrows, ncols = 0, None
    for line in lines:
        ncoords = len([predicate(v) for v in line.split()])
        if ncols is None:
            ncols = ncoords
        else:
            assert ncoords == ncols, '{}: Inconsistent dimension'.format(name)
        nrows += 1
    return nrows, ncols


def lines(f):
    """Yield all lines in a single block."""
    for line in f:
        line = line.strip()
        if line:
            yield line
        else:
            break


def clean_properties(props):
    new_props = {}
    for name, value in props.items():
        if isinstance(value, str):
            if value.startswith('#'):
                value = int(value[1:])
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

        try:
            value = int(value)
        except (ValueError, TypeError):
            pass

        new_props[name] = value
    return new_props


def field_properties(lines):
    """Parse a field block."""
    props, mapping, stepping = {}, {}, False
    for line in lines:
        if line.startswith('%STEP'):
            stepping = True

        if not stepping:
            assert line.startswith('%')
            try:
                name, value = line[1:].split(maxsplit=1)
                props[name.lower()] = value
            except ValueError:
                props[line[1:].lower()] = None

        if stepping and line.startswith('%STEP'):
            stepid = int(line.split()[-1])
            mapping[stepid] = []
        elif stepping:
            mapping[stepid].extend(int(v.strip()) for v in line.split(',') if v.strip())

    return clean_properties(props), mapping


def properties(lines):
    """Split a block into properties and contents."""
    props, cont = {}, []
    for line in lines:
        if line.startswith('%'):
            try:
                name, value = line[1:].split(maxsplit=1)
                props[name.lower()] = value
            except ValueError:
                props[line[1:].lower()] = None
        else:
            cont = [line]
            break

    return clean_properties(props), chain(cont, lines)


def blocks(f):
    """Yield all blocks in a file."""
    ignore = ['glviewstateinfo']

    classes = {
        'internalstring': InternalString,
        'nodes': Nodes,
        'elements': Elements,
        'results': Results,
        'glviewgeometry': Geometry,
        'glviewdisplacement': Displacement,
        'glviewscalar': Scalar,
        'glviewvector': Vector,
    }

    line = next(f)
    assert line.startswith('*VTF-'), 'File is not a valid ASCII VTF file'

    for line in f:
        if line.startswith('*'):
            block_type, block_id = line[1:].split()
            block_type = block_type.lower()
            block_id = int(block_id)
            if block_type not in ignore:
                yield classes[block_type](block_id, lines(f))


class VTFFile:

    def __init__(self, f):
        self.nodes = {}
        self.strings = {}
        self.elements = {}
        self.results = {}
        self.displacements = {}
        self.scalars = {}
        self.vectors = {}
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
                assert self.geometry is None, 'Multiple geometry blocks'
                self.geometry = block
            elif isinstance(block, Displacement):
                self.displacements[block.blkid] = block
            elif isinstance(block, Scalar):
                self.scalars[block.blkid] = block
            elif isinstance(block, Vector):
                self.vectors[block.blkid] = block
            else:
                raise Exception(type(block))

    def fields(self):
        return chain(self.displacements.values(), self.scalars.values(), self.vectors.values())


    def verify(self):
        for blkid, elems in self.elements.items():
            assert elems.nodes_id in self.nodes, 'Elements block {}: Unknown nodes block {}'.format(blkid, elems.nodes_id)

        for blkid, results in self.results.items():
            if results.kind == 'nodal':
                assert results.target in self.nodes, 'Results block {}: Unknown nodes block {}'.format(blkid, results.target)
                assert results.npts == self.nodes[results.target].npts, 'Results block {blkid}: Incorrect size'.format(blkid)
            if results.kind == 'element':
                assert results.target in self.elements, 'Results block {}: Unknown elements block {}'.format(blkid, results.target)
                assert results.npts == self.elements[results.target].nelems, 'Results block {}: Incorrect size'.format(blkid)

        if self.geometry is None:
            raise AssertionError('Geometry block missing')
        for step in self.geometry.mapping.values():
            for blkid in step:
                assert blkid in self.elements, 'Geometry block points to unknown elements block {}'.format(blkid)

        for field in self.fields():
            name = field.__class__.__name__
            for step in field.mapping.values():
                for blkid in step:
                    assert blkid in self.results, '{} block {}: Points to unknown results block {}'.format(name, field.blkid, blkid)

    def summary(self):
        nsteps = max(b.maxstep for b in chain([self.geometry], self.fields()))

        for stepid in range(1, nsteps + 1):
            print('Step {}'.format(stepid))

            eblks = [self.elements[blkid] for blkid in self.geometry.mapping_at(stepid)]
            nblks = [self.nodes[eblk.nodes_id] for eblk in eblks]
            for gpart, (eblk, nblk) in enumerate(zip(eblks, nblks), start=1):
                print('  Element block {}'.format(gpart))
                print('    {} nodes'.format(nblk.npts))
                print('    {} elements'.format(eblk.nelems))

                for field in self.fields():
                    # Check if this field is defined on this geometry part at this step
                    rblks = [self.results[blkid] for blkid in field.mapping_at(stepid)]
                    found = any(
                        (rblk.kind == 'nodal' and self.nodes[rblk.target] in nblks) or
                        (rblk.kind == 'element' and self.elements[rblk.target] in eblks)
                        for rblk in rblks
                    )

                    # Only print if found
                    if found:
                        print("    {}: '{}'".format(field.__class__.__name__, field.name))
