# Extended Wildcards, Robert Barron
import os
import random
import sys
import re

from modules import scripts, script_callbacks, shared
from types import SimpleNamespace

warned_about_files = {}
ewildcard_dir = scripts.basedir()
sequential_state = {}

wildcard_parser = None

class ExtendedWildcardsScript(scripts.Script):
    
    flags = { }
    variables = { }

    def title(self):
        return "Extended wildcards"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def compute_weight(self, str):
        pair = str.split("!!")
        if len(pair) == 2:
            (choice, weight) = pair
            scale = 1
            weight = weight.strip()
            if weight.endswith('%'):
                pair[1] = pair[1][:-1]
                scale = -0.01   # convert percent 0..100 to 0..1, and make it negative as a flag
                   
            if len(pair[1]) >= 1 and pair[1].replace('.','',1).isdigit():
                return [ pair[0], float(pair[1]) * scale ]

        return [ str, 1.0 ]

    def process_prefix(self, text, gen, generators):
        assert isinstance(text, str)
        # use the default generator if no leading @
        if not text.startswith("@"):
            return (text, gen)

        # override which generator to use
        if text.startswith("@@@@"):
            return (text[4:], generators.batchfull)
        elif text.startswith("@@@"):
            return (text[3:], generators.batch)
        elif text.startswith("@@"):
            return (text[2:], generators.fullrand)
        else:
            return (text[1:], generators.normal)


    def alternation_process(self, s, neg, gen, generators):

        # we need to handle nesting to handle "[ ... | ...]" inside "< | >" properly

        def get_simple_token(t):
            return t[0].strip() if len(t) == 1 else ""

        def treeprocess(t, neg, rgen,generators):
            firstchar = t[0][:1]
            if firstchar == '(' or firstchar == '[':
                for i in range(1,len(t),2):
                   t[i],neg = treeprocess(t[i], neg, rgen, generators)
            elif firstchar == '<':
                if len(t) >= 5 and t[2] == ':':  # < foo : bar > or < foo : bar : baz >
                    token = get_simple_token(t[1])
                    value = get_simple_token(t[3])
                    if token == "hasflag" and len(t)==7:
                        if value in self.flags:
                            return treeprocess(t[5], neg, rgen, generators);
                        else:
                            return ("",neg)
                    if token == "hasntflag" and len(t)==7:
                        if value not in self.flags:
                            return treeprocess(t[5], neg, rgen, generators);
                        else:
                            return ("",neg)
                    if token == "setflag" and len(t)==5:
                        self.flags[value] = None
                        return ("",neg)
                    if token == "unsetflag" and len(t)==5:
                        self.flags.pop(value, None)
                        return ("",neg)
                    if token == "getvar" and len(t)==5:
                        if value in self.variables:
                            return treeprocess(self.variables[value], neg, rgen, generators)
                        else
                            return ("",neg)
                    if token == "setvar" and len(t)==7:
                        self.variables[value] = t[5]
                        return ("",neg)
                for i in range(1,len(t),2):
                   t[i],neg = treeprocess(t[i], neg, rgen, generators)
            elif firstchar == '{':
                t[1][0],localgen = self.process_prefix(t[1][0], rgen, generators)
                n = len(t) // 2    # number of choices
                choice = localgen.randrange(n)
                t,neg = treeprocess(t[1+2*choice], neg, localgen, generators) # @TODO: can just return this directly
                t = [t]
            else:
                # even entries are plain text
                for i in range(0,len(t),2):
                   t[i],neg = self.leaf_process(t[i], neg, rgen, generators)
                # odd entries are tree nodes
                for i in range(1,len(t),2):
                   t[i],neg = treeprocess(t[i], neg, rgen, generators)
            return ("".join(t),neg)

        tree = miniparser_parse(wildcard_parser,s)
        return treeprocess(tree, neg, gen, generators)

    def nonrecursive_process(self, s, neg, gen, generators):
        # parse things that our parser doesn't handle, like ~~foo~~ and !foo!
        # replace items like ~~foo~~ with empty string 50% of the time
        # this is for historical reasons, "{|foo}" is better, so retire ~~
        # before release. then switch !foo! to <!foo> and we have no parse-breaking syntax
        all = s.split("~~")
        # todo: pythonic would be
        #   all[1::2] = [f(x) for x in all[1::2]]
        # but not sure how to make that work
        #
        for i in range(1, len(all), 2):
            if all[i] =="@INDEX":
                all[i] = str(generators.index);
            else: 
                all[i], this_gen = self.process_prefix(all[i], gen, generators)
                if this_gen.random() < 0.5:
                    all[i] = ""
        s = "".join(all)

        # look for negative prompts -- it's very important this not run before choices are made,
        # but if we do it in leaf_process then it can't contain any tree operators like () or [],
        # so for now we leave it here where it works for wildcard choices but not {} choices
        all = s.split("!")
        for i in range(1, len(all), 2):
            neg += all[i]
            all[i] = ""
        s = "".join(all)

        return (s,neg)

    def leaf_process(self, s, neg, gen, generators):
        # handle numeric ranges
        if ":@" in s or "$@" in s:
            # match something like "... :@ 0.5-0.7"
            separators = r"(?:-|:|\.\.)"       # - or : or ..
            mynumber = r"\d*\.\d*|\d+\.?\d*"   # 234.57 or .57 or 234
            arr = re.split(f"[:$](@+[dix]*)\\s*({mynumber})\\s*{separators}\\s*({mynumber})", s)
            # explicitly, the regex is:
            #   : or $
            #   @ or @@ or @@@               (or more, this is captured as arr[i])
            #   any of d | i | x             (default, integer, no-colon)
            #
            #   [optional whitespace]
            #   a floating point number      (this is captured as arr[i+1]
            #   [optional whitespace]
            #
            #   - or : or ..
            #
            #   [optional whitespace]
            #   a floating point number      (this is captured as arr[i+2]
            #   [optional whitespace]
            #
            for i in range(1,len(arr),4):
                suffix,this_gen = self.process_prefix(arr[i], gen, generators)
                if "d" in suffix: # use default generator
                    this_gen = gen
                if "i" in suffix:
                    value = this_gen.randint(int(arr[i+1]), int(arr[i+2]))
                    arr[i+1] = str(value)
                else:
                    value = this_gen.uniform(float(arr[i+1]), float(arr[i+2]))
                    arr[i+1] = f"{value:1.2f}"
                arr[i] = "" if "x" in suffix else ":"
                arr[i+2] = ""
            s = "".join(arr)

        return (s,neg)

    def replace_wildcard(self, text, neg, gen, generators):
        if " " in text or len(text) == 0:
            return text

        sequence_count = None
        if text.startswith("@@@@@"):
            sequence_count = 1
            group = re.compile("@@@@@:?(\d*):?(.*)").match(text)
            if len(group[1]) > 0:
                sequence_count = int(group[1])
            text = group[2]

        text,this_gen = self.process_prefix(text, gen, generators)
        if text is None:
            return ("","")

              
        replacement_file = os.path.join(ewildcard_dir, "wildcards", f"{text}.txt")
        if os.path.exists(replacement_file):
            with open(replacement_file, encoding="utf8") as f:

                # read the list of alternatives, but make sure we output which file is bad if there's a problem, since we keep hitting utf-8 issues
                try:
                    choices = f.read().splitlines()
                except Exception as err:
                    print( f"Processing file {text}.txt" )
                    raise err
                     
                # strip out comments
                old_choices = choices
                choices = [] 
                for str in old_choices:
                    comment = str.find("#")
                    if comment == 0:
                        pass  # if line is entirely empty, discard it so it doesn't count as an empty choice
                    else:
                        if comment > 0:
                           str = str[:comment]
                        choices.append(str)

                if len(choices) == 0:
                    return ("",neg)

                discard_marker = "!!0"  # a line with 0 weight has no effect, so if the user happens to have a line with this, that's ok

                # perform indentation-concatenation
                for i in range(len(choices)-2,-1,-1):
                    if choices[i+1].startswith(" "):
                        choices[i] = choices[i] + choices[i+1]
                        choices[i+1] = discard_marker

                # explicitly discard the lines marked as discard
                choices = [x for x in choices if x != discard_marker ]

                # find their relative weights
                choices = list(map(self.compute_weight, choices))

                # measure relative values of weights and percents
                sum = 0.0
                percent_sum = 0.0
                for i in range(len(choices)):
                    if choices[i][1] >= 0:
                        sum += choices[i][1]
                    else:
                        percent_sum += -choices[i][1]

                # determine what weight the percentages should get:
                # (note that percentages are already converted from 0..100 to 0..1)
                #
                # The percentage parts should get some total weight called percent_weight_total
                #   total_weight = percent_weight_total + sum
                #
                # That weight should be the target percentage
                #   percent_weight_total / total_weight = percent_sum
                #
                # Express one in terms of the other:
                #   percent_weight_total = percent_sum * total_weight
                #
                # Plug into first equation and solve:
                #   total_weight = percent_sum * total_weight + sum
                #   total_weight * (1 - percent_sum) = sum
                #   total_weight = sum / (1 - percent_sum)

                # handle degenerate cases
                if percent_sum > 1.0:
                    percent_sum = 1.0
                if percent_sum >= 0.999 and sum > 0:
                    percent_sum = 0.999
                if sum == 0:
                    percent_sum = 1.0

                if percent_sum == 0.0:
                    percent_weight_scale = 0.0
                elif percent_sum == 1.0:
                    percent_weight_scale = 1.0
                else:
                    total_weight = sum / (1 - percent_sum)
                    percent_weight_total = percent_sum * total_weight
                    percent_weight_scale = percent_weight_total / percent_sum

                # convert probabilities to cumulative distribution function (CDF)
                sum = 0.0
                for i in range(len(choices)):
                    if choices[i][1] >= 0:
                        sum += choices[i][1]
                    else:
                        sum += -choices[i][1] * percent_weight_scale
                    # replace probability by CDF, except if probability is 0 in which case use invalid CDF value
                    choices[i][1] = sum if choices[i][1] != 0 else -1

                if sum == 0:
                    return (text,neg)

                if sequence_count is not None:
                    state = sequential_state.get(text)
                    if state is None:
                        state = [ 0, 0 ]

                    n = state[0]

                    state[1] += 1
                    if state[1] >= sequence_count:
                        state[0] += 1
                        if state[0] >= len(choices):
                            state[0] = 0
                        state[1] = 0

                    sequential_state[text] = state
                else:
                    # select point in CDF
                    rand = this_gen.uniform(0,sum)
                    n = 0;
         
                    # return first item which is greater than point
                    for i in range(0,len(choices)):
                        if choices[i][1] >= rand:
                            n = i
                            break

                if n < len(choices):
                    x = choices[n]
                    # process anything that doesn't require recursion
                    refined = self.nonrecursive_process(x[0], neg, this_gen, generators)
                    refined = self.alternation_process(refined[0], refined[1], this_gen, generators)
                    # process anything that requires recursion
                    return self.process_string(refined[0],refined[1], this_gen, generators) # recurse looking for more __

                # not reached
                return (text,neg);
        else:
            if replacement_file not in warned_about_files:
                print(f"File {replacement_file} not found for the __{text}__ wildcard.", file=sys.stderr)
                warned_about_files[replacement_file] = 1

        return (text,neg)

    def process_string(self, str, neg, gen, generators):
        arr = str.split("__")
        for i in range(1, len(arr), 2):
            both = self.replace_wildcard(arr[i], neg, gen, generators)
            arr[i] = both[0]
            neg = both[1]
        return ("".join(arr), neg)

    def process(self, p):
        global wildcard_parser
        wildcard_parser = miniparser_build(["()", "[]", "<:>", "{|}"])
        
        original_prompt = p.all_prompts[0]
        generators = SimpleNamespace(
             normal    = random.Random(), 
             batch     = random.Random(),
             fullrand  = random.Random(),
             batchfull = random.Random(),
             index     = 0
        )

        if not shared.opts.wildcards_random_seed:
             batch = random.Random(p.all_seeds[0])

        # for same seed, force all randoms to use the same generator
        # this guarantees you get the exact same result if you turn on same_seed,
        # even if you then change which generator certain elements use
        # (if we seeded them all from the same seed, they'd always generate
        # the same value within a batch, but sticking in @s would change the
        # output, though it would still remain same as long as you didn't touch @s)
        if shared.opts.wildcards_same_seed:
            generators.batchfull = generators.batch
            generators.normal    = generators.batch
            generators.fullrand  = generators.batch

        gen_state1 = generators.batch    .getstate()
        gen_state2 = generators.batchfull.getstate()

        for i in range(len(p.all_prompts)):
            generators.batch    .setstate(gen_state1)
            generators.batchfull.setstate(gen_state2)

            if not shared.opts.wildcards_random_seed:
                generators.index = i
                if not shared.opts.wildcards_same_seed:
                    print(p.all_seeds[i])
                    generators.normal.seed(p.all_seeds[i])

            self.flags = { }
            self.variables = { }
            prompt = (p.all_prompts[i], "")
            prompt = self.nonrecursive_process(prompt[0], prompt[1], generators.normal, generators)
            prompt = self.alternation_process(prompt[0], prompt[1], generators.normal, generators)
            both = self.process_string(prompt[0], prompt[1], generators.normal, generators)
            both = (" ".join(both[0].split()), " ".join(both[1].split()))
            p.all_prompts[i] = both[0]
            # this is causing crashes
            print("Result: " + p.all_prompts[i])
            if shared.opts.wildcards_allow_negative:
                p.all_negative_prompts[i] += both[1]
                print("Negative: " + both[1])

        if original_prompt != p.all_prompts[0]:
            p.extra_generation_params["Wildcard prompt"] = original_prompt
        if original_prompt.startswith("@RSEQ"):
            sequential_state.clear()

def on_ui_settings():
    shared.opts.add_option("wildcards_same_seed"     , shared.OptionInfo(False, "Use same seed for all images in batch, regardless of @"     , section=("wildcards", "Wildcards")))
    shared.opts.add_option("wildcards_random_seed"   , shared.OptionInfo(False, "Use different seed for all images in batch, regardless of @", section=("wildcards", "Wildcards")))
    shared.opts.add_option("wildcards_allow_negative", shared.OptionInfo(False, "Let !foo! syntax to add to negative prompt (can crash if batch size > 1)", section=("wildcards", "Wildcards")))

script_callbacks.on_ui_settings(on_ui_settings)



# rb miniparser
import re

# compile the grammar into a more efficient form for parsing
def miniparser_build(grammar):

  # normalize:
  #   convert things like ["(:)", "(|)"] to [ "(:|)" ]
  parser_builder = {}
  for x in grammar:
    begin = x[0]
    end = x[-1]
    separators = x[1:-1]
    current = parser_builder.get(begin, end)
    assert current[-1] == end # all productions must use the same end token for each begin token
    current = separators + current
    parser_builder[begin] = current

  # now split up the separators and end chars for efficiency  
  begin = "" ; separators = [] ; end = ""
  for k,v in parser_builder.items():
    begin += k
    end   += v[-1]
    separators += [ v[:-1] ]

  # build the list of one-token characters in regexp charset format
  token_charset   = "".join(set("".join(grammar)))
  escaped_charset = "".join(("\\"+char) if (char in r"\-[]") else char for char in token_charset)

  return ( begin, separators, end, escaped_charset )

def miniparser_parse(parser, s):
  #print("tokenizer: " + s)
  tokens = re.split("([" + parser[3] + "])", s)
  tree,_ = miniparser_parse_text(parser, tokens,0, "", " at top level")
  return tree

def miniparser_parse_text(parser, prompt_tokens, i, stopchars, context):
  assert i % 2 == 0
  text = [ prompt_tokens[i] ]
  i += 1

  while i < len(prompt_tokens):
    assert i % 2 == 1

    # we're now at an explicit token
    tok = prompt_tokens[i]

    # check if we're at the end of this text block
    # (tok can't be the empty string, so 'in' is safe)
    if tok in stopchars:
      if len(text) == 3 and text[0]=="" and text[2]=="":
        text = text[1]  # node just contained one child, so replace it
      return ( text, i ) # didn't consume i after all

    rulenum = parser[0].find(tok)
    if rulenum >= 0:
      delimiters = parser[1][rulenum];
      endchar = parser[2][rulenum]
      node,i = miniparser_parse_grammar_production(parser, prompt_tokens, i, delimiters, endchar, "inside "+tok+endchar+" expression") 
      text.append(node)
      #assert i % 2 == 0  # this can fail if we've hit an error
      if i < len(prompt_tokens):
          text.append(prompt_tokens[i])
          i += 1
    else:
      # token is an ending token that's unmatched or a delimiter from a different type
      if tok in parser[2]:
        print(f'Found a bare "{tok}" {context}.' + (f' Followed by "{prompt_tokens[i+1]}"' if i+1 < len(prompt_tokens) else ''))
      # append it to last string chunk, along with next string chunk
      text[-1] = text[-1] + tok + prompt_tokens[i+1]
      i += 2

  #assert i % 2 == 1 this can fail if we've hit an error

  # if we built a text node containing just some other node and no text, optimize that out
  if len(text) == 3 and text[0]=="" and text[2]=="":
    return (text[1],i)
  return (text, i)

def miniparser_parse_grammar_production(parser, prompt_tokens, i, separators, endtok, context):
  assert i % 2 == 1
  contents = [ prompt_tokens[i] ]
  i += 1

  # parse string up to first separator
  inner,i = miniparser_parse_text(parser, prompt_tokens, i, separators+endtok, context)
  contents.append(inner)

  if i < len(prompt_tokens):

    # now parse out separator-delimited tokens

    tok = prompt_tokens[i]
    if tok == endtok:
      return (contents+[tok], i+1)

    # turn any other unused separators into plain strings
    stop = endtok + tok

    while i < len(prompt_tokens):
      assert i % 2 == 1
      inner,i = miniparser_parse_text(parser, prompt_tokens, i+1, stop, context)
      contents = contents + [tok, inner]
      if i == len(prompt_tokens):
        return (contents,i)
      if prompt_tokens[i] == endtok:
        contents = contents + [endtok]
        return (contents, i+1)

  print(f'Missing "{endtok}" {context}')
  contents.append("") # missing end token to keep lists odd length
  i += 1
  return (contents, i)
