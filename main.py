from memory_profiler import profile
@profile
def main():
    print("Hello from app-007!")
    list_A = [{"name":"A", "Address":{"door":"11", "internal":{"a":1}}}]
    
    import copy

    list_B = copy.deepcopy(list_A)
    list_B[0]["Address"]["door"] = "99"
    print(list_A)
    print(list_B)

if __name__ == "__main__":
    main()
