class TagStreamParser:
    TAG_STATES = {
        "<answer>": "in_answer",
        "</answer": "outside",
        "<meta>": "in_meta",
        "</meta>": "outside"
    }
 
    MAX_TAG_LEN = max(len(t) for t in TAG_STATES)
 
    def __init__(self):
        self.buffer = [] # raw buffer
        self.visible_buffer = [] # <answer> content
        self.current = [] # chunk buffer
        self.state = "outside" # outside | in_answer | in_meta
        self.tag_buffer = "" # partial tag matching
 
    def feed(self, chunk: str):
        self.buffer.append(chunk)
 
        for ch in chunk:
            self.tag_buffer += ch
 
            if len(self.tag_buffer) > self.MAX_TAG_LEN:
                self.tag_buffer = self.tag_buffer[-self.MAX_TAG_LEN:]
           
            self.current.append(ch)
 
            matched_tag = None
            for tag, new_state in self.TAG_STATES.items():
                if self.tag_buffer.endswith(tag):
                    matched_tag = tag
                    self.state = new_state
                    self.tag_buffer = ""
                    self.current.clear()
                    break
           
            if matched_tag:
                continue
 
            # Detect tag boundaries even if split across chunks
            if len(self.current) > self.MAX_TAG_LEN:
                safe_char = self.current.pop(0)
                if self.state == "in_answer":
                    self.visible_buffer.append(safe_char)
 
    def get_visible_text(self):
        return "".join(self.visible_buffer)
 
    def get_raw(self):
        return "".join(self.buffer)
 