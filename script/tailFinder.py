# AUTOGENERATED! DO NOT EDIT! File to edit: 04_RTS_identification.ipynb (unless otherwise specified).

__all__ = ['AlternativeTerminalFinder', 'TailFinderWrapper']

# Cell

import warnings
import pandas as pd
from collections import defaultdict, Counter
from interlap import InterLap
from joblib import Parallel, delayed
from time import strftime
from tqdm import tqdm
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from .utils import Vividict


# Cell

class AlternativeTerminalFinder:
	def __init__(self, chrom, strand, corrected_read_splicing, read_info, min_count_tss_tes, max_sil = 0):

		self.chrom = chrom
		self.strand = strand
		self.corrected_read_splicing = corrected_read_splicing
		self.polya_lst = read_info[2]
		self.count = read_info[3]
		self.fsm = read_info[4]
		self.collapsed_ID = read_info[5]
		self.min_count_tss_tes = min_count_tss_tes
		self.max_sil = max_sil
		self.polya_count = sum(self.polya_lst)
		if self.strand == '+':
			self.rss_lst = read_info[0]
			self.res_lst = read_info[1]
		else:
			self.rss_lst = read_info[1]
			self.res_lst = read_info[0]

	def optimal_k(self, end_list):
		max_sil = self.max_sil
		k_optimal = 1
		df = pd.DataFrame(end_list, columns=['tts'])
		with warnings.catch_warnings(record=True) as w:
			warnings.filterwarnings("error")
			for k in range(2, 5):
				try:
					gmm = GaussianMixture(n_components=k,random_state=0).fit(df)
					labels = gmm.predict(df)
					curr_sil = silhouette_score(df, labels, metric='euclidean')
					if max_sil < curr_sil:
						max_sil = curr_sil
						k_optimal = k
				except:
					k_optimal = k-1
					break
		return df, k_optimal

	def terminal_cluster(self):
		outlist = [self.chrom, self.strand, self.corrected_read_splicing, self.fsm, self.count, self.polya_count, self.collapsed_ID]
		for idx, tail_lst in enumerate([self.rss_lst, self.res_lst]):

			if idx == 0:
				min_dis = 50
				polya_lst = []
			else:
				min_dis = 24
				polya_lst = self.polya_lst

			if len(tail_lst) == 1:
				if idx == 0:
					outlist.extend([tail_lst[0],[tail_lst[0]]])
				else:
					polya_tag = True if polya_lst[0] else False
					outlist.extend([tail_lst[0], [tail_lst[0]], polya_tag])
			else:
				apa_dict = {}
				polya_tag = False
				df, k_optimal = self.optimal_k(tail_lst)
				gmm = GaussianMixture(n_components=k_optimal,random_state=0).fit(df)
				labels = gmm.predict(df)
				df['labels'] = labels
				clusters = {k:v for k, v in Counter(df['labels']).items() if v > 2}
				clusters = dict(sorted(clusters.items(), key=lambda e: e[1], reverse=True))

				if sum(polya_lst)/(self.count) >=0.4:
					df['polya'] = polya_lst
					for key, value in clusters.items():
						if df[(df['labels']==key)&(df['polya']==True)].shape[0]/df[df['labels']==key].shape[0] >= 0.2:
							if apa_dict:
								apa_count = df[df['labels']==key]['tts'].value_counts().tolist()[0]
								if apa_count >= self.min_count_tss_tes:
									apa_site = df[df['labels']==key]['tts'].value_counts().index[0]
									for tmp_site,tmp_count in apa_dict.copy().items():
										if abs(tmp_site-apa_site) < min_dis and apa_count > tmp_count[0]:
											apa_dict[apa_site] = [apa_count, value]
											apa_dict.pop(tmp_site)
											break
										elif abs(tmp_site-apa_site) < min_dis and apa_count == tmp_count[0] and value > tmp_count[1]:
											apa_dict[apa_site] = [apa_count, value]
											apa_dict.pop(tmp_site)
											break
										elif abs(tmp_site-apa_site) < min_dis:
											pass
											break
										else:
											apa_dict[apa_site] = [apa_count, value]
							else:
								apa_count = df[df['labels']==key]['tts'].value_counts().tolist()[0]
								if apa_count >= self.min_count_tss_tes:
									apa_site = df[df['labels']==key]['tts'].value_counts().index[0]
									apa_dict[apa_site] = [apa_count, value]
						if apa_dict:
							polya_tag = True
				else:
					for key, value in clusters.items():
						if apa_dict:
							apa_count = df[df['labels']==key]['tts'].value_counts().tolist()[0]
							if apa_count >= self.min_count_tss_tes:
								apa_site = df[df['labels']==key]['tts'].value_counts().index[0]
								for tmp_site,tmp_count in apa_dict.copy().items():
									if abs(tmp_site-apa_site) < min_dis and apa_count > tmp_count[0]:
										apa_dict[apa_site] = [apa_count, value]
										apa_dict.pop(tmp_site)
										break
									elif abs(tmp_site-apa_site) < min_dis and apa_count == tmp_count[0] and value > tmp_count[1]:
										apa_dict[apa_site] = [apa_count, value]
										apa_dict.pop(tmp_site)
										break
									elif abs(tmp_site-apa_site) < min_dis:
										pass
										break
									else:
										apa_dict[apa_site] = [apa_count, value]
						else:
							apa_count = df[df['labels']==key]['tts'].value_counts().tolist()[0]
							if apa_count >= self.min_count_tss_tes:
								apa_site = df[df['labels']==key]['tts'].value_counts().index[0]
								apa_dict[apa_site] = [apa_count, value]

				if apa_dict:
					apa_site = list(apa_dict.keys())
					end = apa_site[0]
				else:
					if sum(polya_lst)/(self.count) >=0.4:
						if df[df['polya'] == True].shape[0]/df.shape[0] >= 0.2:
							polya_tag =True
						df = df[['tts','polya']].value_counts().reset_index(name='counts')
						df = df.pivot(index='tts', columns='polya', values='counts')
						df = df.reset_index(level=['tts'])
						df = df.fillna(0)
						if False not in df:
							df[False] = 0
						df['ratio'] = df[True]/(df[False]+df[True])
						if self.strand == '+':
							df = df.sort_values(['ratio',True, 'tts', False], ascending=[False,False,False,True])
						else:
							df = df.sort_values(['ratio',True, 'tts', False], ascending=[False,False,True,True])
					else:
						df = df['tts'].value_counts().reset_index()
						df.columns = ['tts', 'counts']
						if (self.strand == '+' and idx == 1) or (self.strand == '-' and idx == 0):
							df = df.sort_values(['counts','tts'], ascending=[False,False])
						elif (self.strand == '+' and idx == 0) or (self.strand == '-' and idx == 1):
							df = df.sort_values(['counts','tts'], ascending=[False,True])
					end = df['tts'].iloc[0]
					apa_site = [end]
				if idx == 0:
					outlist.extend([end, apa_site])
				else:
					outlist.extend([end, apa_site, polya_tag])
		return outlist


# Cell

class TailFinderWrapper:
	def __init__(self, collected_multi_exon_read, min_count_tss_tes, thread):
		self.collected_multi_exon_read = collected_multi_exon_read
		self.min_count_tss_tes = min_count_tss_tes
		self.thread = thread

	def job_precompute(self):
		precompute_list = []
		for (chrom, strand), read_dict in self.collected_multi_exon_read.items():
			for corrected_read_splicing, read_info in read_dict.items():
				precompute_list.append(AlternativeTerminalFinder(chrom, strand, corrected_read_splicing, read_info, self.min_count_tss_tes))
		
		return precompute_list

	def run(self):
		precompute_list = self.job_precompute()
		with Parallel(n_jobs = self.thread) as parallel:
			results_lst = parallel(delayed(lambda x:x.terminal_cluster())(job) for job in tqdm(precompute_list, desc = f'{strftime("%Y-%m-%d %H:%M:%S")}: Calculating pupative TSS and TES for collapsed read'))
		
		return results_lst
	
	def return_extremum(self, strand, entry):
		
		if strand == '+':
			extremum = max(entry)
		else:
			extremum = min(entry)
		return extremum

	def result_collection(self):
		results_lst = self.run()
		processed_collected_multi_exon_read = Vividict()
		three_prime_exon = defaultdict(set)
		for result in results_lst:
			chrom, strand, corrected_read_splicing, fsm, total_count, polya_count, collapsed_ID, start, as_site, end, apa_site, polya_tag = result
			extremum = self.return_extremum(strand, apa_site)
			if strand == '+':
				three_prime_exon[(chrom, strand)].add((corrected_read_splicing[-1],extremum))
			else:
				three_prime_exon[(chrom, strand)].add((extremum, corrected_read_splicing[0]))
			processed_collected_multi_exon_read[(chrom, strand)][corrected_read_splicing] = [start, end, total_count, polya_count, fsm, polya_tag, as_site, apa_site, collapsed_ID]
		
		# sort by read exon number

		for branch in processed_collected_multi_exon_read:
			tmp_dict = {}
			for k in sorted(processed_collected_multi_exon_read[branch], key=len, reverse=True):
				tmp_dict[k] = processed_collected_multi_exon_read[branch][k]
			processed_collected_multi_exon_read[branch] = tmp_dict

		# convert three_prime_exon dict to interlap structure
		for i in three_prime_exon:
			t = list(three_prime_exon[i])
			three_prime_exon[i] = InterLap()
			three_prime_exon[i].update(t)

		return processed_collected_multi_exon_read, three_prime_exon