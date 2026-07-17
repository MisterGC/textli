# Mathematics in textli — a cheatsheet

Open this file with `textli examples/math.md` and press `⌘R` — every
formula below is plain pandoc math in the source (`$…$` inline, `$$…$$`
display), typeset on render. It doubles as a tour of the TeX constructs
textli sets.

## Inline math

Inline math rides the sentence: the mass–energy relation $E = mc^2$, a
subscript $x_i$, a descender $y_j$ sitting on the baseline, and a compact
text-style sum $\sigma^2 = \frac{1}{N}\sum_{i=1}^{N}(x_i - \mu)^2$ that
stays part of the line.

## Fractions & binomials

`\frac` stacks, `\binom` counts, and they nest:

$$\binom{n}{k} = \frac{n!}{k!\,(n-k)!}$$

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

$$\cfrac{1}{1+\cfrac{1}{1+\cfrac{1}{1+\dotsb}}} = \frac{\sqrt{5}-1}{2}$$

## Roots & powers

`\sqrt` takes an optional index, powers and indices stack freely:

$$\sqrt[3]{x^2 + 1}, \qquad a^{b^c} \neq (a^b)^c, \qquad x_{i,j}^{2n}$$

## Sequences, sums & products

Limits under the operator in display style (`\lim`, `\sum`, `\prod`):

$$\lim_{n\to\infty}\left(1 + \frac{1}{n}\right)^n = e$$

$$\sum_{k=0}^{\infty} r^k = \frac{1}{1-r} \quad (|r| < 1), \qquad
n! = \prod_{k=1}^{n} k$$

## Calculus

Derivatives, partials and the integral family (`\int`, `\iint`, `\oint`):

$$\frac{\mathrm{d}}{\mathrm{d}x}\, e^{\lambda x} = \lambda e^{\lambda x},
\qquad
\frac{\partial^2 u}{\partial x^2} + \frac{\partial^2 u}{\partial y^2} = 0$$

$$\int_0^\infty e^{-x^2}\,\mathrm{d}x = \frac{\sqrt{\pi}}{2}, \qquad
\iint_D f(x,y)\,\mathrm{d}A, \qquad
\oint_C \vec{F}\cdot\mathrm{d}\vec{r}$$

## Linear algebra

Matrix flavors — `pmatrix`, `bmatrix`, `vmatrix` — plus norms:

$$A = \begin{pmatrix} \alpha & \beta \\ \gamma & \delta \end{pmatrix},
\qquad
I = \begin{bmatrix} 1 & 0 \\ 0 & 1 \end{bmatrix},
\qquad
\begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc$$

$$\left\lVert x \right\rVert_2 = \sqrt{\sum_i x_i^2}$$

## Piecewise & multi-line

`cases` for piecewise definitions, `aligned` for shared alignment points:

$$|x| = \begin{cases} x & x \ge 0 \\ -x & x < 0 \end{cases}$$

$$\begin{aligned}
(a+b)^2 &= (a+b)(a+b) \\
        &= a^2 + 2ab + b^2
\end{aligned}$$

## Sets & logic

Set operations, quantifiers and arrows:

$$A \cap B \subseteq A \cup B, \qquad \emptyset \subset \mathbb{R}, \qquad
\bigcup_{i=1}^{n} A_i$$

$$\forall \varepsilon > 0\; \exists \delta > 0 :
|x| < \delta \Rightarrow |f(x)| < \varepsilon$$

$$f\colon X \to Y, \qquad x \mapsto x^2, \qquad A \iff B$$

## Decorations

Accents and braces annotate without leaving math:

$$\bar{x}, \quad \hat{y}, \quad \tilde{z}, \quad \dot{q}, \quad \vec{v}$$

$$\overbrace{1 + 2 + \cdots + n}^{n(n+1)/2}, \qquad
\underbrace{x + x + \cdots + x}_{n\ \text{times}}$$

## Functions & named results

Upright function names, Greek, and `\text` for prose inside math:

$$\sin^2\theta + \cos^2\theta = 1, \qquad \ln e^x = x, \qquad
e^{i\pi} + 1 = 0$$

$$P(A \mid B) = \frac{P(B \mid A)\,P(A)}{P(B)} \quad \text{(Bayes)}$$

## What stays prose

The rules are pandoc's, so ordinary dollars never turn into math: it costs
$5 and $10 in total, a literal \$ escapes, and code keeps its dollars —
`price = $x$` — as does a fenced block:

```sh
echo $HOME $$
```

## Review works on math

Annotations and math compose: a comment
{==on the $E = mc^2$ term==}{>>check the units — should this be per mole?<<}
keeps its formula rendered inside the highlighted span.
