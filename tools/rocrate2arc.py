from arctrl.arc import ARC

def arc_to_rocrate_json(rocrate_input_path: str, arc_path: str):
    # Lade ARC aus Datei
    with open(rocrate_input_path, "r", encoding="utf-8") as f:
        arc = ARC.from_rocrate_json_string(f.read())
    
    arc.Write(arc_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python rocrate2arc.py <input.json> <output.arc>")
        sys.exit(1)
    arc_to_rocrate_json(sys.argv[1], sys.argv[2])