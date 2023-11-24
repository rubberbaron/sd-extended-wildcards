# Stable Diffusion Extended Wildcards extension

## Introduction

A custom extension for
[AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
that expands on the stable-diffusion-webui-wildcards with many new features.

Some of the features are similar or identical to [sd-dynamic-prompts](https://github.com/adieyal/sd-dynamic-prompts),
but there are many differences. If you are happy with sd-dynamic-prompts you probably won't find
anything of interest here. I made this for me, I'm just releasing it in case anyone else wants it.

## Quick list of features

   * `__examplefile__` - a random line is chosen from "wildcard filenames" surrounded by double underscores 
      * wildcard files can contain references to wildcards, allowing recursive template expansion
      * weights can be assigned to each line, prioritizing how frequently they're chosen
      * choices can extend across multiple lines, or be commented out
      * wildcard files can optionally generate their choices sequentially
   * `{red|green|blue}` - a single text is chosen from within curly brackets with multiple options separated by the pipe character, 
      * `{}` choices can be nested, for example `{a {red|blue} ball|a {gold|silver} ring}`
      * `{}` choices can contain references to wildcard files and wildcard choices can contain `{}` choices
      * weights in `{}` with same syntax as sd-dynamic-prompts; implicit empty choice
   * random numbers within a range can be generated
      * `(foo:@0.8-1.0)` - choose a random real number to create a prompt like `(foo:0.87)`
      * `[foo:bar:@10-20]` - choose a random integer to create a prompt like `[foo:bar:13]`
      * `$@1940-2020` - choose a random integer
   * multiple random number generators chosen by the prompt text
      * choices can depend on the seed
      * choices can be completely random, regardless of seed
      * choices can be consistent within a batch (they depend on the seed of the first generation in the batch)
      * choices can be consistent within a batch, but independent of seeds
      * choices can be made from one of several global seeds, which will remain consistent until explicitly overriden
      * automatically update the global seeds periodically
      * you can also use global settings to force fully-random or always-the-same generators
   * test and set flags and variables
      * `<set:foo>` - set a flag which can be tested later in the prompt
      * `<test:foo:some example text if true>` - test if a flag was set earlier in the prompt
      * `<set:foo:this is some text>` - store a string in a variable for later use
      * `<get:foo>` - retrieve the string from the variable and add to the prompt
      * `<set!:foo:this is some text>` - eager evaluation of text
      * these can be nested, e.g. `<get>` and `<test>` inside `<set>`
      * `<FOO:bar>` - equivalent to `<test:FOO:bar>`, only works for all-caps variable names

## Detailed description

### Wildcards

To choose a random line from a file "example.txt", put the text `__example__` in your prompt.

No processing is performed on the filename, so you *can't* do something like `__{foo|bar}__`
to choose between two files. __This will not work.__

#### Sequential (cyclic) selection

To make Extended Wildcards choose sequentially from the options in the file (which
sd-dynamic-prompts calls a "cyclical sampler"), use a `$` after the double-underscore:
`__$example__`. When the end of the file is reached, it will return to the beginning
and start over.

You can make each option repeat some number of times before advancing to the next
in the sequence. For example, suppose you had a batch size of 4 and wanted every
item in the batch to use the same choice from the file, then you could use the
syntax `__$4$example__`, and it would repeat each choice from `example.txt` 4 times.

If the lines in the wildcard file have integer weights using "!!", when sequential
processing, those weights are treated as the number of times to repeat each choice,
overriding the repeat count specified above.

### Wildcards file format

#### Comments

The basic format is to have one choice per line in the file. Additionally, you can have
Python-style comments:

```
# imdb's "most popular celebs"
Cillian Murphy
Margot Robbie
Christopher Nolan   # are directors really celebrities?!?
Greta Gerwig
Florence Pugh
```

#### Choices spanning multiple lines

Single choices can be split across multiple lines by indenting every line after the first of
the choice. The indentation doesn't have to be consistent; any amount of indentation makes
the line be considered part of the choice from the prevoous line.

For example, the following file has four choices:

```
# an example for multi-line choices; this line is not a choice, but the next empty line is a choice

This is the
  second choice which has
  been split across three lines.
# The first choice was an empty line,
# so it will generate no text at all 25% of the time
#
This is the
       third choice which
  has been split
       # still going
  across six lines,
  depending how you count

  This is a fourth choice, being appended to the previous empty line.
  This is not recommended, but is included in this example just to show every case.
  
  This also continues the fourth choice, because the line above appears empty but contains leading whitespace.
  Again, not recommended.
```

Note that an empty line is a valid choice. However, a line containing only "#" is not
considered a choice, it is skipped entirely. A line containing an indented "#"
continues the previous choice. There's not really a consistent rule for these;
they just do what seems to be the most useful.

#### Weights

You can assign weights to each choice, causing them to be more or less likely to be chosen,
by ending the line with `!!` and a number. The default weight is 1. If a choice extends
across multiple lines, the weight must go on the last line of the choice.

```
red       # implicitly 1
green!!2
blue !!3  # since the sum is 6, blue will occur 50% of the time
```

You can also assign percentages:
```
red  !!2.7
green!!9.2
blue !!50%
```

In this example, blue will be chosen 50% of the time, and the rest of the time, red or
green will be chosen in appropriate proportion to the values.

The general rule is that all options with percentage weights are chosen that percentage of the
time, as long as the sum of the percentage weights is 100% or less. Whatever percentage is left over
(100 minus the sum) is split up amongst the other choices in proportion to their weights.
If the percentages exceed 100%, then choices without percentage weights will never be
chosen, and choices with percentage weights will be chosen in proportion to their
percentages (but less frequently than the actual percentages). Hopefully, most of the
time this is just intuitively what you expect.

For example, while developing and testing a wildcard file, you can set the weight
of a line to "!!99999999%" to force it to be nearly always chosen. If no other choices
have percentage weights, it will always be chosen. If other choices have normal percentage
weights, the weight for this line is so large that there is only an infinitesimal chance
one of the other choices will be chosen.

If the percent weights don't add up to 100%, or regular weights don't add up to at least 1,
then an implicit empty choice is added to the list, and it is assigned the missing weight.
However, if you use both percentages and regular weights, no empty choice is added.

So:

```
red  !!25%
green!!25%
blue !!25%
```
will output nothing 25% of the time, as will
```
red  !!0.25
green!!0.25
blue !!0.25
```
but
```
red  !!33%
green!!0.25
blue !!0.25
```
will output each of red, blue, and green approximately 1/3rd of the time.

This implicit-empty-choice behavior is optional and can be disabled in the settings, and
is included primarily for consistency with variants (discussed below).

#### Whitespace

Extra spaces and newlines in wildcard expansions are automatically converted to a single space, but spaces
are not added. For example, in this example:
```
red  !!1
green!!2
blue !!3
```
the result of choosing the first line will add `"red "` with a space
to the prompt, but the result of choosing the second line will add `"green"` without a space to the prompt.
This is intentional as it's possible you might want to intentionally cause things to be assembled with no gaps.

## Variants

Variants choices are contained in `{}` and are separated by the pipe symbol, `|`. If there are N choices
in a variant, each will be chosen with equal likelihood. Variant options can themselves contain variants,
as in
```
{a {red|green|blue} ball|a {gold|silver} ring}
```
which chooses between equally between `a {red|green|blue} ball` and `a {gold|silver} ring`, and then
chooses equally from amongst the subchoices. This means there is a 16.7% chance each to
get `a red ball`, `a green ball`, or `a blue ball`, and a 25% chance each to
get `a gold ring` or `a silver ring`.

Choices in a variant can be assigned a weight by prefixing them with the weight and `::`, for example
```
a {0.25::red|0.25::green|0.25::blue} ball
```

All the same rules about fractional weights and percentage weights from wildcard files apply
to variant choices as well. The "implicit empty option" also applies, and cannot be disabled
in settings, so the above choice will produce "a ball" 25% of the time.

## Randomness generator

You can override the source of randomness on each of the operations that use randomness.

There are five primary randomness generators:
   * `__@n@examplefile__` choices depend on the seed; this is the default (**N**ormal)
   * `__@b@examplefile__` consistent within a single batch, usoing the first seed of the batch (**B**atch)
   * `__@s@examplefile__` settable seed randomness, the same on every run until the seed is changed (**S**ettable Seed)`
   * `__@r@examplefile__` completely random, regardless of seed (**R**andom)
   * `__@br@examplefile__` completely random, but consistent within a single batch (**B**atch **R**andom)

There's also a syntax to specify the default behavior explicitly which I don't think is useful:
   * `__@d@examplefile__` use whichever generator would have been used otherwise

Each of the syntaces for random-based prompt alteration support specifying a generator:
   * `__@s@examplefile__`
   * `{@s@red|blue|green}`
   * `(foo:@s@0.0-1.0)` (see below)
   * `$@s@1920-1999` (see below)

The motivation for the `@b@` batch generator is to allow random selections for Loras. In
a batch, all prompts will use the same Loras and the same weights. If they're chosen randomly
in different prompts, one of them is used (I think the first, but I'm not sure). This could
be ok, but for two issues: first, if a construct like `{<lora:mylora:1>|||}` is meant to enable a Lora
about 25% of the time, it actualy puts it in each prompt 25% of the time, so a batch of 4 is
very likely to contain it. Second, it breaks reproducibility; if a Lora weight is set randomly
like `<lora:mylora:@0.2-0.8>`, then each prompt in a batch will get a different weight, but only
one of those weights will be used, and the one recorded in the info will be wrong.
All of the prompts with the wrong weight will save their PNG info with the wrong weight,
and then using the PNG info to reconstruct the prompt will not work. Using `@b@` causes
all of the prompts in a batch to generate the same prompt text, so those elements will be
consistent.

### Randomness nesting

Choosing a randomness generator like `@b@` sets the "current" randomness generator used while
processing the wildcard file. Any variant choices or wildcard references inside the file will
also use the chosen randomness generator, unless they choose a generator explicitly using `@`.
This randomness generator only applies with that file; text that follows after the wildcard
reference will return to the previous "current" generator.

Likewise, if the choices in a construction like `{@b@red|blue}` contain additional variants
or wildcard references, those will also use the `@b@` generator, unless they've been set to
use a generator explicitly.

In addition, on the settings tab for Extended Wildcards, you can set the settings for Extended Wildcards and
force all choices to be completely random (like `@@`), or to force all choices to come
from the seed (like `@`), regardless of whether the choices have `@b@` or `@s@` or etc.

## Settable seed random generators

There are actually ten explicitly seeded generators:
   * `__@s@examplefile__`
   * `__@s0@examplefile__` specified seed #0, the same as `__@s@examplefile__`
   * `__@s1@examplefile__` specified seed #1
   * `__@s2@examplefile__` specified  seed #2
   * ...
   * `__@s9@examplefile__` specified  seed #9

These 10 generators are restored after every image, so if they are used by the same prompt
elements in the same way in every image, they will always generate the exact same prompt text.

You can make each of the 10 generators get a new random seed after a fixed number of generations,
using the `List of automatic reseed periods for setseeds @s0@..@s9@` textbox in the
`Extended Wildcards` accordion. Each generator can run at a different period.

You can manually set the seed for a settable seed generator from prompt text.
Write something like
   * `<setseed:123456>` - sets seed #0 to 123456
   * `<setseed3:123456>` - sets seed #3 to 123456
   * `<setseed6:*>` - sets seed #6 to a new randomly chosen seed

I don't know how useful it is, but it does allow you to, for example, randomly re-seed
the generators at random intervals, or in more complicated patterns than the simple
periodic reseeding.

For example, suppose we have a wildcard file named "resetseed1_70_30.txt":
```
<setseed1:*>
!!69
<setseed1:*>
!!29
```

And the prompt beings with `__$resetseed1_70_30__`, then every 100 images, seed #1 would
be randomized twice, once after the first 70 images, and then again after the last 30.
On the other hand, `__resetseed1_70_30__` without the `$` would have a 2% chance of
rerandomizing seed #1 every time it's run.

## Random number generation

Random number generation is triggered by the strings `:@` or `$@`. When one of these
strings is found, starting immediately after the `:` or `$` the following is checked for:

   * If the trigger is `:@`, a `:` is included in the result
   * If the trigger is `$@`, no `$` is included in the result
   * The presence of an `@b@`style generator is checked for, and the rules above for "Random generator choice" are applied for this random number.
     (It does not change the current random generator for anything else in the prompt).
   * A following pair of numbers is parsed. The numbers can be separated by `-`, `..`, or `:`
      * If the numbers are both integers, an integer is generated
      * If either number has a decimal point, a real number is generated
   * A number is generated between the two specified values. If it's a real number, two decimal digits are output.
      * `:@0.2-.4` might generate `:0.37`
      * `$@200..400` might generate `372`
