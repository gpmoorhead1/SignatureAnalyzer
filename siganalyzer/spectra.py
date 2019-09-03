import itertools, pandas as pd

_acontext = itertools.product('A', 'CGT', 'ACGT', 'ACGT')
_ccontext = itertools.product('C', 'AGT', 'ACGT', 'ACGT')
context96 = dict(zip(map(''.join, itertools.chain(_acontext, _ccontext)), range(1, 97)))

def calc_muts_spectra(input_maf, hgfile='../../dat/hg19.2bit', out_file='sampleMutSpectra.txt'):
    """
    Calculate mutational context.
    Finds each type of mutation and creates a categorical variable. Saves this output as
    the mutational spectra file.
    """
    hg = TwoBitFile(hgfile)
    sample_muts_context = defaultdict(lambda: [0]*96)

    df = pd.read_csv(input_maf, sep='\t').loc[:,['Tumor_Sample_Barcode','Variant_Type','Chromosome','Start_position','Reference_Allele','Tumor_Seq_Allele2','ttype']]
    df = df[df['Variant_Type']=='SNP']

    for idx,row in df.iterrows():
        ref_base = row['Reference_Allele'].lower()
        new_base = row['Tumor_Seq_Allele2'].lower()

        if ref_base == '-' or new_base == '-':
            continue
        if len(ref_base) > 1 or len(new_base) > 1:
            continue

        pos = int(row['Start_position'])
        chromosome = str(row['Chromosome'])

        if chromosome == '23':
            chromosome = 'X'
        elif chromosome == '24':
            chromosome = 'Y'
        elif chromosome == 'MT':
            chromosome = 'M'

        abc = hg['chr'+chromosome][pos-2:pos+1].lower()

        if abc[1] != ref_base and ref_base != '--':
            print(abc, ref_base)
            print('non-matching reference.')
            continue

        pat = (row['Tumor_Sample_Barcode'], row['ttype'])

        try:
            sample_muts_context[pat][encode(abc, new_base)] += 1
        except:
            ## because of Ns
            print("Because of Ns")
            continue

    hdr = list(MUTATION_INDICES.items())
    hdr.sort(key=lambda x:x[1])
    index_col = ['patient', 'ttype'] + [i[0][0]+'-'+i[0][1] for i in hdr]

    df = pd.DataFrame.from_dict(sample_muts_context).T
    df = df.reset_index()
    df.columns = index_col
    df.to_csv(out_file, sep='\t',index=None)
    

def get_spectra_from_maf(maf):
    """
    Attaches context categories to maf and gets counts of contexts for each sample
    Args:
        maf: Pandas DataFrame of maf

    Returns:
        Pandas DataFrame of maf with context category attached
        Pandas DataFrame of counts with samples as columns and context as rows
    """
    maf = maf.copy()
    maf['sample'] = maf['Tumor_Sample_Barcode']
    if 'Variant_Type' in maf.columns:
        maf = maf.loc[maf['Variant_Type'] == 'SNP']
    else:
        maf = maf.loc[maf['Reference_Allele'].apply(lambda k: len(k) == 1 and k != '-') &
                      maf['Tumor_Seq_Allele2'].apply(lambda k: len(k) == 1 and k != '-')]
    ref = maf['Reference_Allele'].str.upper()
    alt = maf['Tumor_Seq_Allele2'].str.upper()
    context = maf['ref_context'].str.upper()
    n_context = context.str.len()
    mid = n_context // 2
    complements = {'A': 'T', 'C': 'G', 'G': 'C', 'T': 'A'}
    contig = pd.Series([r + a + c[m - 1] + c[m + 1] if r in 'AC'
                        else complements[r] + complements[a] + complements[c[m - 1]] + complements[c[m + 1]]
                        for r, a, c, m in zip(ref, alt, context, mid)], index=maf.index)
    try:
        maf['context96.num'] = contig.apply(context96.__getitem__)
    except KeyError as e:
        raise KeyError('Unusual context: ' + str(e))
    maf['context96.word'] = contig
    spectra = maf.groupby(['context96.num', 'sample']).size().unstack().fillna(0).astype(int)
    return maf, spectra