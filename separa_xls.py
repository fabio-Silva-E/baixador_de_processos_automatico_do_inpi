import pandas as pd

# arquivo de entrada
arquivo_entrada = "MP_Procurar_logo_diferente.xlsx"  # ou .csv

# se for Excel:
df = pd.read_excel(arquivo_entrada, engine="openpyxl")

# se for CSV, use isso no lugar:
# df = pd.read_csv("dados.csv", sep=";", encoding="utf-8-sig")

# garante que coluna existe e evita erro com NaN
df["site"] = df["site"].fillna("").astype(str)

# separa quem tem site
com_site = df[df["site"].str.strip() != ""]

# separa quem não tem site
sem_site = df[df["site"].str.strip() == ""]

# salva arquivos
com_site.to_excel("com_site.xlsx", index=False)
sem_site.to_excel("sem_site.xlsx", index=False)

print("Arquivos gerados com sucesso!")