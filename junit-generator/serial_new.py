def _serialize_xml(write, elem, encoding, qnames, namespaces, level=0):
    def _indent_gen(i):
        return ' ' * (2 * i)
    tag = elem.tag
    text = elem.text
    if tag == '![CDATA[':
        # CDATA. Do NOT escape special characters
        write("<%s%s\n]]>\n" % (tag, str_to_unicode(text).encode(encoding)))
    elif tag is ET.Comment:
        write("%s<!--%s-->\n" % (_indent_gen(level),
                                ET._encode(text, encoding)))
    elif tag is ProcessingInstruction:
        write("%s<?%s?>\n" % (_indent_gen(level),
                                ET._encode(text, encoding)))
    else:
        tag = qnames[tag]
        if tag is None:
            if text:
                string = ET._escape_cdata(text, encoding)
                if len(elem) > 0:
                    string = "%s%s\n" % (_indent_gen(level+1), string)
                write(string)
            for e in elem:
                _serialize_xml(write, e, encoding, qnames, None, level+1)
        else:
            write("%s<%s" % (_indent_gen(level+1), tag))
            items = elem.items()
            if items or namespaces:
                if namespaces:
                    for v, k in sorted(namespaces.items(),
                                       key=lambda x: x[1]):  # sort on prefix
                        if k:
                            k = ":" + k
                        write(" xmlns%s=\"%s\"" % (
                            k.encode(encoding),
                            ET._escape_attrib(v, encoding)
                            ))
                for k, v in sorted(items):  # lexical order
                    if isinstance(k, ET.QName):
                        k = k.text
                    if isinstance(v, ET.QName):
                        v = qnames[v.text]
                    else:
                        v = ET._escape_attrib(v, encoding)
                    write(" %s=\"%s\"" % (qnames[k], v))
            if text or len(elem):
                write(">")
                if len(elem) > 0:
                    write("\n")
                if text:
                    string = ET._escape_cdata(text, encoding)
                    if len(elem) > 0:
                        string = "%s%s\n" % (_indent_gen(level+1), string)
                    write(string)
                for e in elem:
                    _serialize_xml(write, e, encoding, qnames, None, level+1)
                write("%s</%s>\n" % (_indent_gen(level+1), tag))
            else:
                write(" />\n")
    if elem.tail:
        write("%s%s" % (_indent_gen(level),
                        ET._escape_cdata(elem.tail, encoding)))
