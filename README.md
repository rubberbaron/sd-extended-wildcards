# Stable Diffusion Extended Wildcards extension

## Status

Although this has been posted, it is in early access. THere's no documentation and some things may change. Use at your own risk.

## Introduction

A custom extension for
[AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
that expands on the stable-diffusion-webui-wildcards with many new features. Some of these are similar to
[sd-dynamic-prompts](https://github.com/adieyal/sd-dynamic-prompts)
but there are many differences.

## Features

   * `__examplefile__` - a random line is chosen from "wildcard filenames" surrounded by double underscores 
      * wildcard files can contain references to wildcards, allowing recursive template expansion
      * weights can be assigned to each line, prioritizing how frequently they're chosen
      * choices can extend across multiple lines, or be commented out
   * `{red|green|blue}` - a single text is chosen from within curly brackets with multiple options separated by the pipe character, 
      * `{}` choices can be nested, for example `{a {red|blue} ball|a {gold|silver} ring}`
      * `{}` choices can contain references to wildcard files and wildcard choices can contain `{}` choices
      * TODO: support weights in `{}` with same syntax as sd-dynamic-prompts
   * random numbers within a range can be generated
      * `(foo:@0.8-1.0)` - choose a random real number to create a prompt like `(foo:0.87)`
      * `[foo:bar:@i10-20]` - choose a random integer to create a prompt like `[foo:bar:13]`
   * multiple random number generators
      * by default, choices and random numbers are keyed to the seed for each image. this can be overridden:
         * `__@examplefile__` choices depend on the seed
         * `__@@examplefile__` completely random, regardless of seed
         * `__@@@examplefile__` consistent within a single batch
         * `__@@@@examplefile__` consistent within a single batch but independent of seed
      * you can also use global settings to force fully-random or always-the-same generators
   * test and set flags
      * `<setflag:foo>` - set a flag which can be tested later in the prompt
      * `<hasflag:foo:some example text>` - test if a flag was set earlier in the prompt
   * set and retrieve text from variables
      * `<setvar:foo:this is some text>` - store a string in a variable for later use
      * `<getvar:foo>` - retrieve the string from the variable and add to the prompt
      * these can be nested with flags, for example `<hasflag:cringe:<getvar:cringedata>>`

## Detailed description


## Example

```
color photograph, sci-fi, {||<setflag:male>}
  <hasntflag:male: {beautiful|pretty|perfect|}>
  [{[human|alien|human]|[alien|human|human]|[human|human|alien]|[human|alien-skinned]|||}:@0.1-0.25]
  <hasntflag:male: {__sf_woman__ ,|woman}>
  <hasflag:male:$@ix18-45yo male>
  {exotic|high fashion|fashionable|unfashionable|fancy|wild|unique|elaborate|||}
  <hasntflag:male:{revealing|skimpy|sexy||||||} {gown|dress|bodysuit|outfit|clothing|costume|cosplay}>
  <hasflag:male:{clothing|costume|outfit|skimpy clothing|skimpy outfit|sexy costume|cosplay|clothing}>,
  {transparent {chest|arms|neck|thighs|arms}||{shiny|metallic|glossy|glowing|neon|}|__gp3s/sf_wearing_details__||},
  <getvar:performance>
  __sf_performer_location__  {|||__gpt3/sf_place_details__}
```

`sf_woman.txt` contains:
```
{||__sf_multicolored_hair__} :@ix21-27yo __sf_ethnicity__ woman with __sfhair__ __breasts2__ !!75%
{||__sf_multicolored_hair__} :@ix28-36yo __sf_ethnicity__ woman with __sfhair__ __breasts2__ !!25%
```

`breasts2.txt` contains
```
!!1
!huge breasts, large breasts!                 # put huge/large in negative, so as to tend towards smaller breasts
with medium breasts !huge breasts!
with large breasts                 !!0.35 
with huge breasts                  !!0.15
```
etc.