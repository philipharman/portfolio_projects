# SDG Bill Tracking

## Overview
- General purpose: Lobbyists can use this tool to identify legislation that is pertinent to any given UN SDG, and from there identify which legislative offices to contact.
- Usage requirements: Users can…
    - Filter by SDG / SDG goal, and legislative body (i.e. federal, state).
    - Answer questions like:
        - What bills are currently in the works regarding SDG XYZ?
        - Can I get the abstract of bill X?
        - Within body chamber X, which legislators are sponsoring the most legislation regarding issue ABC?

## Building a Corpus

- Each Goal has between five and ten Targets, with each target having a handful of Indicators.
- I downloaded the full set of Goals, Targets and Indicators from the [UN Stats divsion](https://unstats.un.org/sdgs/indicators/indicators-list/).
- After some light prep work, here's my cleaned dataframe:

| SDG                                             | Target                                                                                                                                                               | Indicator                                                                                                                                           |
|:------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------|
| Goal 1. End poverty in all its forms everywhere | 1.1 By 2030, eradicate extreme poverty for all people everywhere, currently measured as people living on less than $1.25 a day                                       | 1.1.1 Proportion of the population living below the international poverty line by sex, age, employment status and geographic location (urban/rural) |
| Goal 1. End poverty in all its forms everywhere | 1.2 By 2030, reduce at least by half the proportion of men, women and children of all ages living in poverty in all its dimensions according to national definitions | 1.2.1 Proportion of population living below the national poverty line, by sex and age                                                               |
| Goal 1. End poverty in all its forms everywhere | 1.2 By 2030, reduce at least by half the proportion of men, women and children of all ages living in poverty in all its dimensions according to national definitions | 1.2.2 Proportion of men, women and children of all ages living in poverty in all its dimensions according to national definitions                   |
| ... | ... | ... |

The idea is then to build a descriptive body of text for each Target. We'll do that here by grouping together each Target and its corresponding Indicators into a single line-separated string, which is what we'll then feed into the model. 

Here's an example of the input for Target no. 1.2:

```
1.2 By 2030, reduce at least by half the proportion of men, women and children of all ages living in poverty in all its dimensions according to national definitions

1.2.1 Proportion of population living below the national poverty line, by sex and age

1.2.2 Proportion of men, women and children of all ages living in poverty in all its dimensions according to national definitions
```