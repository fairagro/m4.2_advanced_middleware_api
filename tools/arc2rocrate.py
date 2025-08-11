from arctrl.arc import ARC

def arc_to_rocrate_json(arc_path: str, rocrate_output_path: str):
    # Lade ARC aus Datei
    arc = ARC.load(arc_path)
    
    # Exportiere als RO-Crate JSON-Objekt
    rocrate = arc.ToROCrateJsonString()
    
    # Schreibe die JSON-Repräsentation in eine Datei
    with open(rocrate_output_path, "w", encoding="utf-8") as f:
        f.write(rocrate)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python arc2rocrate.py <input.arc> <output.json>")
        sys.exit(1)
    arc_to_rocrate_json(sys.argv[1], sys.argv[2])