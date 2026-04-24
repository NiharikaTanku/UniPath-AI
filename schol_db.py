# schol_db.py - Comprehensive scholarships database by country
SCHOLARSHIPS = [
 # INDIA - Government
 {"name":"National Overseas Scholarship","country":"India","type":"Government","provider":"Ministry of Social Justice","amount":"Full tuition + living","eligibility":"SC/ST/OBC students for Masters/PhD abroad","deadline":"Oct 2026","website":"https://nosmsje.gov.in"},
 {"name":"AICTE PG Scholarship","country":"India","type":"Government","provider":"AICTE","amount":"₹12,400/month","eligibility":"GATE-qualified PG students","deadline":"Rolling","website":"https://www.aicte-india.org"},
 {"name":"PM Vidyalaxmi Scheme","country":"India","type":"Government","provider":"Govt of India","amount":"Interest subsidy on education loans","eligibility":"Students from EWS families","deadline":"Rolling","website":"https://www.vidyalakshmi.co.in"},
 {"name":"INSPIRE Fellowship","country":"India","type":"Government","provider":"DST","amount":"₹80,000/month for PhD","eligibility":"PhD researchers in natural sciences","deadline":"Rolling","website":"https://www.online-inspire.gov.in"},
 {"name":"Maulana Azad National Fellowship","country":"India","type":"Government","provider":"UGC","amount":"₹31,000-35,000/month","eligibility":"Minority community MPhil/PhD students","deadline":"Mar 2026","website":"https://www.ugc.ac.in"},
 # USA - Government & University
 {"name":"Fulbright-Nehru Fellowship","country":"USA","type":"Government","provider":"USIEF","amount":"Full tuition + living + travel","eligibility":"Indian students for Masters/PhD in USA","deadline":"Jun 2026","website":"https://www.usief.org.in"},
 {"name":"Hubert H. Humphrey Fellowship","country":"USA","type":"Government","provider":"US State Dept","amount":"Full funding for 1 year","eligibility":"Mid-career professionals","deadline":"Jun 2026","website":"https://www.humphreyfellowship.org"},
 {"name":"Stanford Knight-Hennessy Scholars","country":"USA","type":"University","provider":"Stanford University","amount":"Full tuition + stipend + travel","eligibility":"Graduate applicants to Stanford","deadline":"Oct 2026","website":"https://knight-hennessy.stanford.edu"},
 {"name":"MIT Abdul Latif Jameel Fund","country":"USA","type":"University","provider":"MIT","amount":"Need-based full funding","eligibility":"Admitted MIT students","deadline":"Rolling","website":"https://sfs.mit.edu"},
 {"name":"Harvard Financial Aid","country":"USA","type":"University","provider":"Harvard","amount":"Need-based (avg $76,000/yr)","eligibility":"Admitted students (family income < $75K = free)","deadline":"Feb 2026","website":"https://college.harvard.edu/financial-aid"},
 # UK - Government & University
 {"name":"Chevening Scholarship","country":"UK","type":"Government","provider":"UK Foreign Office","amount":"Full tuition + living + travel","eligibility":"1-year Masters in UK (2yr work exp)","deadline":"Nov 2026","website":"https://www.chevening.org"},
 {"name":"Commonwealth Scholarship","country":"UK","type":"Government","provider":"CSC","amount":"Full tuition + living + travel","eligibility":"Masters/PhD from Commonwealth countries","deadline":"Dec 2026","website":"https://cscuk.fcdo.gov.uk"},
 {"name":"GREAT Scholarships","country":"UK","type":"Government","provider":"British Council","amount":"£10,000 tuition fee reduction","eligibility":"Indian students for PG in UK","deadline":"May 2026","website":"https://study-uk.britishcouncil.org/scholarships/great-scholarships"},
 {"name":"Rhodes Scholarship","country":"UK","type":"University","provider":"Oxford University","amount":"Full tuition + living (£18,180/yr)","eligibility":"Outstanding graduates for Oxford PG","deadline":"Jul 2026","website":"https://www.rhodeshouse.ox.ac.uk"},
 {"name":"Gates Cambridge Scholarship","country":"UK","type":"University","provider":"Cambridge University","amount":"Full cost of studying at Cambridge","eligibility":"Non-UK students for PhD/Masters","deadline":"Dec 2026","website":"https://www.gatescambridge.org"},
 # CANADA - Government
 {"name":"Vanier Canada Graduate Scholarship","country":"Canada","type":"Government","provider":"Govt of Canada","amount":"$50,000/yr for 3 years","eligibility":"PhD students","deadline":"Nov 2026","website":"https://vanier.gc.ca"},
 {"name":"Canada-India Research Centre of Excellence","country":"Canada","type":"Government","provider":"Shastri Institute","amount":"Research funding","eligibility":"Indian researchers","deadline":"Varies","website":"https://www.shastriinstitute.org"},
 {"name":"Ontario Trillium Scholarship","country":"Canada","type":"Government","provider":"Ontario Govt","amount":"$40,000/yr for 4 years","eligibility":"International PhD students in Ontario","deadline":"Varies by university","website":"https://www.ontario.ca"},
 {"name":"University of Toronto Lester B. Pearson","country":"Canada","type":"University","provider":"UofT","amount":"Full tuition + books + living for 4 yrs","eligibility":"Outstanding international UG students","deadline":"Nov 2026","website":"https://future.utoronto.ca/pearson"},
 # AUSTRALIA - Government
 {"name":"Australia Awards Scholarship","country":"Australia","type":"Government","provider":"DFAT","amount":"Full tuition + living + travel","eligibility":"Students from developing countries","deadline":"Apr 2026","website":"https://www.dfat.gov.au/people-to-people/australia-awards"},
 {"name":"Destination Australia Scholarship","country":"Australia","type":"Government","provider":"Dept of Education","amount":"$15,000/yr","eligibility":"Students studying in regional Australia","deadline":"Varies","website":"https://www.education.gov.au"},
 {"name":"Melbourne Research Scholarship","country":"Australia","type":"University","provider":"Uni of Melbourne","amount":"Full tuition + $37,000/yr stipend","eligibility":"Research degree students","deadline":"Oct 2026","website":"https://scholarships.unimelb.edu.au"},
 # GERMANY - Government
 {"name":"DAAD Scholarship","country":"Germany","type":"Government","provider":"DAAD","amount":"€934-1,300/month + tuition","eligibility":"Masters/PhD students","deadline":"Oct 2026","website":"https://www.daad.de"},
 {"name":"Deutschlandstipendium","country":"Germany","type":"Government","provider":"German Govt + Private","amount":"€300/month","eligibility":"Talented students at German unis","deadline":"Varies by university","website":"https://www.deutschlandstipendium.de"},
 {"name":"Heinrich Boll Foundation Scholarship","country":"Germany","type":"Government","provider":"Heinrich Boll Foundation","amount":"€934/month + tuition","eligibility":"International students in Germany","deadline":"Mar & Sep","website":"https://www.boell.de"},
 # FRANCE
 {"name":"Eiffel Excellence Scholarship","country":"France","type":"Government","provider":"Campus France","amount":"€1,181/month (Masters)","eligibility":"Non-French students for Masters/PhD","deadline":"Jan 2026","website":"https://www.campusfrance.org/en/eiffel"},
 {"name":"Emile Boutmy Scholarship","country":"France","type":"University","provider":"Sciences Po","amount":"€5,000-16,000/yr","eligibility":"Non-EU students at Sciences Po","deadline":"Apr 2026","website":"https://www.sciencespo.fr/en/emile-boutmy"},
 # JAPAN
 {"name":"MEXT Scholarship","country":"Japan","type":"Government","provider":"Japanese Govt","amount":"Full tuition + ¥143,000/month + travel","eligibility":"International students for UG/PG/Research","deadline":"Apr 2026","website":"https://www.studyinjapan.go.jp/en/smap-stopj-applications-scholarship.html"},
 {"name":"JASSO Scholarship","country":"Japan","type":"Government","provider":"JASSO","amount":"¥48,000-80,000/month","eligibility":"International students in Japan","deadline":"Varies","website":"https://www.jasso.go.jp"},
 # SINGAPORE
 {"name":"Singapore International Graduate Award","country":"Singapore","type":"Government","provider":"A*STAR","amount":"Full tuition + $2,200/month stipend","eligibility":"PhD students in science/engineering","deadline":"Jun & Dec","website":"https://www.a-star.edu.sg/Scholarships/for-graduate-studies"},
 {"name":"NUS ASEAN Undergraduate Scholarship","country":"Singapore","type":"University","provider":"NUS","amount":"Full tuition + living allowance","eligibility":"ASEAN country students","deadline":"Mar 2026","website":"https://www.nus.edu.sg/oam/scholarships"},
 # SOUTH KOREA
 {"name":"Korean Government Scholarship (KGSP)","country":"South Korea","type":"Government","provider":"NIIED","amount":"Full tuition + living + airfare + insurance","eligibility":"International UG/PG students","deadline":"Feb-Mar 2026","website":"https://www.studyinkorea.go.kr"},
 # NETHERLANDS
 {"name":"Holland Scholarship","country":"Netherlands","type":"Government","provider":"Nuffic","amount":"€5,000 one-time","eligibility":"Non-EEA students for Dutch universities","deadline":"Feb 2026","website":"https://www.studyinholland.nl/finances/scholarships/highlighted-scholarships/holland-scholarship"},
 {"name":"Orange Tulip Scholarship","country":"Netherlands","type":"Government","provider":"Nuffic","amount":"Varies (partial to full tuition)","eligibility":"Indian students","deadline":"Varies","website":"https://www.nesoindia.org"},
 # IRELAND
 {"name":"Government of Ireland Postgraduate Scholarship","country":"Ireland","type":"Government","provider":"Irish Research Council","amount":"€16,000/yr + fees","eligibility":"Masters/PhD in Ireland","deadline":"Oct 2026","website":"https://research.ie"},
 # NEW ZEALAND
 {"name":"New Zealand International Doctoral Scholarship","country":"New Zealand","type":"Government","provider":"NZ Govt","amount":"Full tuition + $25,000/yr","eligibility":"International PhD students","deadline":"Jul 2026","website":"https://www.nzidrs.ac.nz"},
 # ITALY
 {"name":"Italian Government Scholarship","country":"Italy","type":"Government","provider":"MAECI","amount":"€900/month","eligibility":"International students for Masters/PhD","deadline":"Varies","website":"https://studyinitaly.esteri.it"},
 {"name":"Bocconi Merit Award","country":"Italy","type":"University","provider":"Bocconi University","amount":"Full tuition waiver","eligibility":"Merit-based for admitted students","deadline":"Jan 2026","website":"https://www.unibocconi.eu/financial-aid"},
 # SPAIN
 {"name":"Spanish Government Scholarship","country":"Spain","type":"Government","provider":"AECID","amount":"Tuition + living allowance","eligibility":"Students from developing countries","deadline":"Varies","website":"https://www.aecid.es"},
 # ARGENTINA
 {"name":"Argentine Government Scholarship","country":"Argentina","type":"Government","provider":"Govt of Argentina","amount":"ARS 90,000/month + health insurance","eligibility":"International students for PG","deadline":"Varies","website":"https://www.argentina.gob.ar/educacion/becas"},
 # BRAZIL
 {"name":"PEC-PG Scholarship","country":"Brazil","type":"Government","provider":"CAPES/CNPq","amount":"Full tuition + R$1,500/month","eligibility":"Students from developing countries for PG","deadline":"Varies","website":"https://www.gov.br/capes"},
 # SWITZERLAND
 {"name":"Swiss Government Excellence Scholarship","country":"Switzerland","type":"Government","provider":"SERI","amount":"CHF 1,920/month + tuition","eligibility":"International postgraduate students","deadline":"Nov 2026","website":"https://www.sbfi.admin.ch"},
 {"name":"ETH Zurich Excellence Scholarship","country":"Switzerland","type":"University","provider":"ETH Zurich","amount":"CHF 12,000/semester + tuition waiver","eligibility":"Outstanding Masters students at ETH","deadline":"Dec 2026","website":"https://ethz.ch/students/en/studies/financial/scholarships.html"},
 # CHINA
 {"name":"Chinese Government Scholarship (CSC)","country":"China","type":"Government","provider":"China Scholarship Council","amount":"Full tuition + living + accommodation","eligibility":"International students for UG/PG/PhD","deadline":"Jan-Apr 2026","website":"https://www.campuschina.org"},
 {"name":"Confucius Institute Scholarship","country":"China","type":"Government","provider":"Hanban","amount":"Full tuition + living + accommodation","eligibility":"Chinese language/culture students","deadline":"Varies","website":"https://www.chinese.cn"},
 # SWEDEN
 {"name":"Swedish Institute Scholarship","country":"Sweden","type":"Government","provider":"Swedish Institute","amount":"Full tuition + SEK 10,000/month + travel","eligibility":"Students from eligible countries for Masters","deadline":"Feb 2026","website":"https://si.se/en/apply/scholarships/"},
 {"name":"KTH Scholarship","country":"Sweden","type":"University","provider":"KTH","amount":"Full/partial tuition waiver","eligibility":"Fee-paying Masters students at KTH","deadline":"Jan 2026","website":"https://www.kth.se/en/studies/fees-and-scholarships"},
 # DENMARK
 {"name":"Danish Government Scholarship","country":"Denmark","type":"Government","provider":"Danish Ministry of Education","amount":"Full/partial tuition waiver + grant","eligibility":"Non-EU students in Denmark","deadline":"Varies","website":"https://studyindenmark.dk/"},
 # HONG KONG
 {"name":"Hong Kong PhD Fellowship Scheme","country":"Hong Kong","type":"Government","provider":"RGC Hong Kong","amount":"HKD 27,600/month + travel","eligibility":"International PhD students","deadline":"Dec 2026","website":"https://cerg1.ugc.edu.hk/hkpfs/"},
 {"name":"HKU Foundation Scholarship","country":"Hong Kong","type":"University","provider":"HKU","amount":"Full tuition + living","eligibility":"Outstanding international students","deadline":"Varies","website":"https://www.hku.hk"},
 # MALAYSIA
 {"name":"Malaysian International Scholarship","country":"Malaysia","type":"Government","provider":"Ministry of Education Malaysia","amount":"Full tuition + living + travel","eligibility":"International PG students","deadline":"Jul 2026","website":"https://biasiswa.mohe.gov.my"},
 # NORWAY
 {"name":"Norwegian Quota Scheme","country":"Norway","type":"Government","provider":"Norwegian Govt","amount":"Full tuition (free) + NOK 12,953/month","eligibility":"Students from developing countries","deadline":"Varies","website":"https://www.studyinnorway.no"},
 # FINLAND
 {"name":"Finnish Government Scholarship Pool","country":"Finland","type":"Government","provider":"Finnish National Agency","amount":"EUR 1,500/month","eligibility":"International doctoral students","deadline":"Feb 2026","website":"https://www.oph.fi"},
 {"name":"Aalto University Scholarship","country":"Finland","type":"University","provider":"Aalto University","amount":"Full/partial tuition waiver","eligibility":"Non-EU Masters students","deadline":"Jan 2026","website":"https://www.aalto.fi"},
 # AUSTRIA
 {"name":"OeAD Scholarship","country":"Austria","type":"Government","provider":"OeAD","amount":"EUR 1,150/month","eligibility":"International students for research/PhD","deadline":"Varies","website":"https://oead.at/en/to-austria/scholarships"},
 # BELGIUM
 {"name":"VLIR-UOS Scholarship","country":"Belgium","type":"Government","provider":"VLIR-UOS","amount":"EUR 1,090/month + tuition + travel","eligibility":"Students from developing countries","deadline":"Feb 2026","website":"https://www.vliruos.be/en/scholarships"},
 # POLAND
 {"name":"Polish NAWA Scholarship","country":"Poland","type":"Government","provider":"NAWA","amount":"PLN 1,500/month + tuition waiver","eligibility":"International students for PG/PhD","deadline":"Varies","website":"https://nawa.gov.pl/en"},
 # PORTUGAL
 {"name":"FCT PhD Scholarship","country":"Portugal","type":"Government","provider":"FCT","amount":"EUR 1,144/month","eligibility":"PhD students in Portugal","deadline":"Varies","website":"https://www.fct.pt"},
 # CZECH REPUBLIC
 {"name":"Czech Government Scholarship","country":"Czech Republic","type":"Government","provider":"MEYS","amount":"Full tuition + CZK 14,000/month","eligibility":"International students","deadline":"Varies","website":"https://www.msmt.cz"},
 # MEXICO
 {"name":"Mexican Government Scholarship","country":"Mexico","type":"Government","provider":"AMEXCID","amount":"Full tuition + MXN 12,000/month","eligibility":"International PG students","deadline":"Varies","website":"https://www.gob.mx/amexcid"},
 # CHILE
 {"name":"Becas Chile Scholarship","country":"Chile","type":"Government","provider":"ANID","amount":"Full tuition + living + travel","eligibility":"International Masters/PhD students","deadline":"Varies","website":"https://www.anid.cl"},
 # TAIWAN
 {"name":"Taiwan Scholarship","country":"Taiwan","type":"Government","provider":"MOE Taiwan","amount":"NTD 15,000-20,000/month + tuition","eligibility":"International degree students","deadline":"Feb-Mar 2026","website":"https://taiwanscholarship.moe.gov.tw"},
 # UAE
 {"name":"Mohammed Bin Rashid Scholarship","country":"UAE","type":"Government","provider":"MBRF","amount":"Full tuition + living","eligibility":"Outstanding students","deadline":"Varies","website":"https://www.mbrf.ae"},
 # RUSSIA
 {"name":"Russian Government Scholarship","country":"Russia","type":"Government","provider":"Ministry of Education Russia","amount":"Full tuition + stipend","eligibility":"International students","deadline":"Varies","website":"https://education-in-russia.com"},
]

def get_scholarships_by_country(country="All"):
    if country == "All":
        return SCHOLARSHIPS
    return [s for s in SCHOLARSHIPS if s["country"].lower() == country.lower()]
