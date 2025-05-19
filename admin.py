from collections import defaultdict

mydict = defaultdict(dict)
mydict["x"] = {"a" : 5, "b" : 9}
mydict["x"].update({"a" : 2, "c" : 4})
mydict["x"]["e"] = 8

dict2 = {"a" : 2, "c" : 4}
dict2["b"] = 6
print(mydict["x"].get("d", 0))
print(dict2["b"])