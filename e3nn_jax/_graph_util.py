from typing import Union

import jax
import jax.numpy as jnp

import e3nn_jax as e3nn


def _distinct_but_small(x: jnp.ndarray) -> jnp.ndarray:
    """Maps the input to the integers 0, 1, 2, ..., n-1, where n is the number of distinct elements in x.

    Args:
        x (``jnp.ndarray``): array of integers

    Returns:
        ``jnp.ndarray``: array of integers of same size
    """
    assert x.ndim == 1
    unique = jnp.unique(x, size=x.shape[0])  # Pigeonhole principle
    return jax.vmap(lambda i: jnp.where(i == unique, size=1)[0][0])(x)


def index_add(
    indices: jnp.ndarray, input: Union[jnp.ndarray, e3nn.IrrepsArray], *, out_dim: int = None, map_back: bool = False
) -> Union[jnp.ndarray, e3nn.IrrepsArray]:
    r"""perform the operation

    ```
    out = zeros(out_dim, ...)
    out[indices] += input
    ```

    if ``map_back`` is ``True``, then the output is mapped back to the input position.

    ```
    return out[indices]
    ```

    Args:
        indices (``jnp.ndarray``): array of indices
        input (``jnp.ndarray`` or `e3nn_jax.IrrepsArray`): array of data
        out_dim (int): size of the output
        map_back (bool): whether to map back to the input position

    Returns:
        ``jnp.ndarray`` or ``e3nn_jax.IrrepsArray``: output

    Example:
       >>> i = jnp.array([0, 2, 2, 0])
       >>> x = jnp.array([1.0, 2.0, 3.0, -10.0])
       >>> index_add(i, x, out_dim=4)
       DeviceArray([-9.,  0.,  5.,  0.], dtype=float32)
    """
    assert indices.shape[0] == input.shape[0]

    if out_dim is None and map_back is False:
        # out_dim = jnp.max(indices) + 1
        raise ValueError("out_dim must be specified if map_back is False")
    if out_dim is not None and map_back is True:
        raise ValueError("out_dim must not be specified if map_back is True")

    if out_dim is None and map_back is True:
        out_dim = indices.shape[0]
        indices = _distinct_but_small(indices)

    x = input
    if isinstance(input, e3nn.IrrepsArray):
        x = input.array

    output = jnp.zeros((out_dim,) + x.shape[1:]).at[indices].add(x)

    if map_back:
        output = output[indices]

    if isinstance(input, e3nn.IrrepsArray):
        return e3nn.IrrepsArray(input.irreps, output)
    return output


def radius_graph(pos, r_max, *, batch=None, size=None, loop=False):
    r"""naive and inefficient version of ``torch_cluster.radius_graph``

    Args:
        pos (``jnp.ndarray``): array of shape ``(n, 3)``
        r_max (float):
        batch (``jnp.ndarray``): indices
        size (int): size of the output
        loop (bool): whether to include self-loops

    Returns:
        ``jnp.ndarray``: src
        ``jnp.ndarray``: dst

    Example:
        >>> key = jax.random.PRNGKey(0)
        >>> pos = jax.random.normal(key, (20, 3))
        >>> batch = jnp.arange(20) < 10
        >>> radius_graph(pos, 0.8, batch=batch)
        (DeviceArray([ 3,  7, 10, 11, 12, 18], dtype=int32), DeviceArray([ 7,  3, 11, 10, 18, 12], dtype=int32))
    """
    r = jax.vmap(jax.vmap(lambda x, y: jnp.linalg.norm(x - y), (None, 0), 0), (0, None), 0)(pos, pos)
    if loop:
        mask = r < r_max
    else:
        mask = (r < r_max) & (r > 0)

    src, dst = jnp.where(mask, size=size, fill_value=-1)

    if batch is None:
        return src, dst
    return src[batch[src] == batch[dst]], dst[batch[src] == batch[dst]]
